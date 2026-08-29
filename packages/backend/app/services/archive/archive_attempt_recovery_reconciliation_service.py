"""不引入工作进程或队列的持久发布意图恢复。"""

from __future__ import annotations

import sqlite3
import shutil
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ...repository.archive_input_snapshot_repository import ArchiveInputSnapshotRepository
from ...repository.archive_attempt_restart_repository import normalize_runtime_after_restart
from ...repository.archive_manifest_repository import (
    ArchiveManifestRepository, ArchiveManifestRepositoryError,
)
from ...repository.archive_publish_intent_repository import ArchivePublishIntentRepository
from ...repository.archive_publish_fence_repository import normalize_active_for_restart, set_status
from ...repository.workbench_database import WorkbenchDatabase
from ...repository.workbench_errors import WorkbenchPersistenceError
from .archive_input_snapshot_files_service import (
    assert_marker, assert_snapshot_tree_safe, make_tree_writable,
    resolve_snapshot_dir, snapshot_name_matches_id,
)
from .archive_manifest_service import validate_manifest_files
from .archive_runtime_service import ArchiveManifestRecord
from .archive_staging_security_service import cleanup_owned_staging
from .archive_publication_identity_service import publication_digest

if TYPE_CHECKING:
    from .archive_attempt_service import ArchiveAttemptService


class _RecoveryTransientError(RuntimeError):
    """证据可能有效，但基础设施读写故障是暂时的。"""


class _RecoveryConflictError(RuntimeError):
    """持久证据已证明此意图无法完成。"""


def recover_after_restart(service: ArchiveAttemptService) -> list[str]:
    interrupted: list[str] = []
    intents = ArchivePublishIntentRepository(service.database)
    runtime_records = normalize_runtime_after_restart(service.database)
    normalize_active_for_restart(service.database)

    for record in runtime_records:
        if intents.get_for_attempt(str(record["attempt_id"])) is None:
            _cleanup_interrupted(service, record)
            interrupted.append(str(record["attempt_id"]))

    # 发布意图而非尝试运行时状态，才是持久化的协调索引。
    # 其中包括发布后基础设施错误遗留的失败尝试。
    for intent in intents.list_unfinished():
        attempt_id = str(intent["attempt_id"])
        try:
            attempt = service.repository.get_internal(attempt_id)
        except WorkbenchPersistenceError:
            continue
        try:
            outcome = _recover_published_intent(service, attempt, intent, intents)
        except _RecoveryTransientError:
            # 运行时状态已中断；保留证据和待处理围栏，供稍后显式验证。
            continue
        except _RecoveryConflictError:
            current = intents.get_for_attempt(attempt_id)
            if current and current.get("publication_status") not in {
                "sealed", "published", "verified",
            }:
                _cleanup_unsealed_publication(service, current)
            if current and current["phase"] != "conflict":
                intents.mark_phase(attempt_id, "conflict")
            if current and current.get("fence_id"):
                try:
                    set_status(service.database, current["fence_id"], "invalidated", "ARCHIVE_EVIDENCE_CONFLICT")
                except WorkbenchPersistenceError:
                    pass
            if attempt_id not in interrupted:
                interrupted.append(attempt_id)
            continue
        if not outcome and attempt_id not in interrupted:
            interrupted.append(attempt_id)
    cleanup_unfinished_snapshots(
        service.database, service.output_root,
    )
    return interrupted


def cleanup_unfinished_snapshot(
    database: WorkbenchDatabase, output_root: str | Path, value: dict[str, Any],
) -> str:
    """仅移除持久记录中由任务精确拥有的复制中或已密封路径。

    即使进程在标记落盘前终止，复制中记录仍是持久所有权证据。下方会在
    受控的旧版或短快照根目录中解析定位符，候选项仅限记录中的精确最终名称
    及其精确的 `.copying` 同级项。
    """
    if value.get("deployment_instance_id") != database.deployment_instance_id:
        raise WorkbenchPersistenceError("ARCHIVE_INPUT_SNAPSHOT_OWNER_MISMATCH")
    snapshot_id = str(value.get("snapshot_id") or "")
    if not snapshot_id:
        raise WorkbenchPersistenceError("ARCHIVE_INPUT_SNAPSHOT_INVALID")
    final = resolve_snapshot_dir(output_root, str(value.get("snapshot_locator") or ""))
    root = final.parent
    expected_final = (root / final.name).resolve(strict=False)
    if final != expected_final or not snapshot_name_matches_id(snapshot_id, final.name):
        raise WorkbenchPersistenceError("ARCHIVE_INPUT_SNAPSHOT_OWNER_MISMATCH")
    copying = root / f".{final.name}.copying"
    marker = root / f".{final.name}.owner.json"
    status = str(value.get("status") or "")
    if status not in {"copying", "invalidated", "sealed"}:
        return "not_required" if status == "cleaned" else "unknown"

    if marker.exists():
        assert_marker(
            marker, snapshot_id, str(value["task_id"]), str(value["attempt_id"]),
            database.deployment_instance_id, str(value["snapshot_root_id"]),
            str(value["marker_token"]),
        )
    elif status == "sealed":
        # 密封输入必须保留其所有者标记，直至正常完成。
        raise WorkbenchPersistenceError("ARCHIVE_INPUT_SNAPSHOT_OWNER_INVALID")

    for candidate in (copying, final):
        if not candidate.exists():
            continue
        if candidate.is_symlink() or candidate.resolve(strict=False).parent != root:
            raise WorkbenchPersistenceError("ARCHIVE_INPUT_SNAPSHOT_OWNER_INVALID")
        assert_snapshot_tree_safe(candidate)
        make_tree_writable(candidate)
        shutil.rmtree(candidate)
    marker.unlink(missing_ok=True)
    ArchiveInputSnapshotRepository(database).mark_cleaned(snapshot_id)
    return "succeeded"


def cleanup_unfinished_snapshots(
    database: WorkbenchDatabase, output_root: str | Path,
) -> list[str]:
    """尽力清理，同时为不安全记录保留持久诊断信息。"""
    repository = ArchiveInputSnapshotRepository(database)
    cleaned: list[str] = []
    for value in repository.list_unfinished():
        try:
            if cleanup_unfinished_snapshot(database, output_root, value) == "succeeded":
                cleaned.append(str(value["snapshot_id"]))
        except (OSError, ValueError, KeyError, WorkbenchPersistenceError):
            # 该行保持复制中/已失效/已密封状态，并由下一次有界恢复流程重试；
            # 绝不删除其所有者根目录之外的内容。
            continue
    return cleaned


def _cleanup_unsealed_publication(
    service: ArchiveAttemptService, intent: dict[str, Any],
) -> None:
    """恢复冲突后，仅移除任务绑定且从未密封的最终候选项。"""
    compressed_root = (service.output_root / "compressed").resolve(strict=False)
    candidate = (compressed_root / str(intent["relative_final_dir"])).resolve(strict=False)
    try:
        candidate.relative_to(compressed_root)
    except ValueError:
        return
    if candidate == compressed_root or not candidate.exists() or candidate.is_symlink():
        return
    try:
        shutil.rmtree(candidate)
    except OSError:
        # 如果清理暂时不可用，持久冲突仍是权威状态；
        # 恢复流程绝不能提升此候选项。
        return


def _cleanup_interrupted(service: ArchiveAttemptService, record: dict[str, Any]) -> None:
    cleanup = cleanup_owned_staging(record, service.staging_root, service.database.deployment_instance_id)
    if cleanup != "not_required":
        error_code = "ARCHIVE_STAGING_CLEANUP_UNKNOWN" if cleanup == "unknown" else None
        if cleanup == "failed":
            error_code = "ARCHIVE_STAGING_CLEANUP_FAILED"
        service.repository.mark_cleanup(record["attempt_id"], cleanup, error_code)


def _recover_published_intent(
    service: ArchiveAttemptService, attempt: dict[str, Any],
    intent: dict[str, Any], intents: ArchivePublishIntentRepository,
) -> bool:
    if any(intent[key] != attempt_value for key, attempt_value in {
        "case_id": attempt["case_id"], "source_id": attempt["source_id"],
        "source_revision": int(attempt["source_revision"]),
        "draft_revision": int(attempt["draft_revision"]),
        "report_fingerprint": attempt["report_fingerprint"],
    }.items()):
        raise _RecoveryConflictError("intent binding mismatch")
    legacy_attempt = (
        attempt.get("task_id") in (None, f"legacy-task-{attempt['attempt_id']}")
        and intent.get("task_id") == f"legacy-task-{attempt['attempt_id']}"
    )
    if (
        ((not legacy_attempt) and (
            not attempt.get("task_id")
            or intent.get("task_id") != attempt.get("task_id")
        ))
        or intent.get("deployment_instance_id") != service.database.deployment_instance_id
        or intent.get("publication_status") not in {"sealed", "published", "verified"}
    ):
        raise _RecoveryConflictError("publication identity missing")
    expected_digest, expected_file_set = publication_digest(intent, intent["public_manifest"])
    if (
        intent.get("publication_digest") != expected_digest
        or intent.get("publication_file_set") != expected_file_set
    ):
        raise _RecoveryConflictError("publication generation mismatch")
    final_dir = (service.output_root / "compressed" / intent["relative_final_dir"]).resolve(strict=False)
    compressed_root = (service.output_root / "compressed").resolve(strict=False)
    try:
        final_dir.relative_to(compressed_root)
    except ValueError as error:
        raise _RecoveryConflictError("intent target outside compressed root") from error
    record = ArchiveManifestRecord(
        intent["manifest_id"], attempt["attempt_id"], intent["archive_fingerprint"],
        intent["public_manifest"], final_dir, 0.0, time.time() + 60,
        publication_id=intent["publication_id"], publication_digest=intent["publication_digest"],
    )
    try:
        if not final_dir.is_dir():
            return False
        integrity_error = validate_manifest_files(record)
    except (OSError, PermissionError) as error:
        raise _RecoveryTransientError() from error
    if integrity_error is not None:
        raise _RecoveryConflictError(integrity_error)
    try:
        service.remove_marker(final_dir)
    except (OSError, PermissionError) as error:
        raise _RecoveryTransientError() from error
    registry = ArchiveManifestRepository(service.output_root, database=service.database)
    try:
        same_manifest = registry.find_by_manifest_id(intent["manifest_id"])
        if any(item.workbench_attempt_id != attempt["attempt_id"] for item in same_manifest):
            raise _RecoveryConflictError("manifest belongs to another attempt")
        indexed = next((item for item in same_manifest if item.workbench_attempt_id == attempt["attempt_id"]), None)
        if indexed is not None and (
            indexed.relative_final_dir != intent["relative_final_dir"]
            or indexed.public_manifest != intent["public_manifest"]
            or indexed.source_key != intent["source_key"]
            or indexed.input_fingerprint != intent["input_fingerprint"]
            or indexed.archive_fingerprint != intent["archive_fingerprint"]
        ):
            raise _RecoveryConflictError("indexed evidence mismatch")
        # 始终根据持久意图重写派生投影。这样也能在崩溃后修复缺失/损坏的索引，
        # 而不会将 JSON 文件视为第二权威来源。
        registry.save(
            source_key=intent["source_key"], input_fingerprint=intent["input_fingerprint"],
            archive_fingerprint=intent["archive_fingerprint"], manifest_id=intent["manifest_id"],
            final_dir=final_dir, public_manifest=intent["public_manifest"],
            workbench_attempt_id=attempt["attempt_id"],
            publication_id=intent["publication_id"],
            publication_digest=intent["publication_digest"],
        )
        if intent["phase"] == "intent_persisted":
            intents.mark_publication_state(attempt["attempt_id"], "published")
            intents.mark_phase(attempt["attempt_id"], "published")
            intent = intents.get_for_attempt(attempt["attempt_id"]) or intent
        if intent["phase"] == "published":
            intents.mark_phase(attempt["attempt_id"], "indexed")
        from .archive_attempt_completion_service import complete_verified
        complete_verified(service, attempt["attempt_id"], registry, record, recovery=attempt["status"] != "succeeded")
        current = intents.get_for_attempt(attempt["attempt_id"])
        if current and current["phase"] == "indexed" and attempt["status"] == "succeeded":
            intents.mark_phase(attempt["attempt_id"], "verified")
        return True
    except _RecoveryConflictError:
        raise
    except (ArchiveManifestRepositoryError, OSError, PermissionError, sqlite3.OperationalError) as error:
        raise _RecoveryTransientError() from error
    except WorkbenchPersistenceError as error:
        if error.code in {
            "ARCHIVE_COMPLETION_EVIDENCE_CONFLICT", "ARCHIVE_COMPLETION_EVIDENCE_INVALID",
            "ARCHIVE_COMPLETION_EVIDENCE_REQUIRED", "ARCHIVE_PUBLISH_TARGET_MISMATCH",
            "ARCHIVE_PUBLISH_INTENT_STATE_INVALID", "ARCHIVE_ATTEMPT_BINDING_STALE",
        }:
            raise _RecoveryConflictError(error.code) from error
        raise _RecoveryTransientError() from error
