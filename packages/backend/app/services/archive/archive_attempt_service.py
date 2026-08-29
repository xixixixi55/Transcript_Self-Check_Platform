"""围绕现有旧版执行器的阶段 1D 归档尝试边界。"""

from __future__ import annotations

import json
import stat
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from ...repository.archive.archive_attempt_repository import ArchiveAttemptRepository
from ...repository.archive.archive_attempt_restart_repository import interrupt_attempt
from ...repository.archive.archive_preparation_repository import ArchivePreparationRepository
from ...repository.archive.archive_context_binding_repository import (
    find_active_binding_for_attempt,
    find_binding,
    report_fingerprint,
)
from ...repository.archive.archive_publish_fence_repository import get as get_fence
from ...repository.archive.archive_publish_intent_repository import ArchivePublishIntentRepository
from ...repository.case_workbench_repository import CaseDraftRepository, CaseShellRepository
from ...repository.source_record_repository import SourceRecordRepository
from ...repository.workbench_database import WorkbenchDatabase, utc_now
from ...repository.workbench_errors import WorkbenchPersistenceError
from .archive_manifest_service import validate_published_manifest
from .archive_staging_security_service import (
    OWNERSHIP_MARKER_NAME,
    cleanup_owned_staging,
    controlled_staging_root_id,
    remove_ownership_marker,
    write_ownership_marker,
)
from .archive_input_snapshot_service import (
    SealedInputSnapshot, assert_sealed_input, cleanup_sealed_input_snapshot,
    create_sealed_input_snapshot, load_sealed_input_snapshot,
)
from ...repository.workbench_serialization import validate_opaque_id

if TYPE_CHECKING:
    from .archive_manifest_service import ArchiveFileIdentity


def _expired(value: object) -> bool:
    if value is None:
        return False
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed <= datetime.now(timezone.utc)
    except (TypeError, ValueError):
        return True


@dataclass(frozen=True)
class ArchivePublicationSnapshot:
    report: dict[str, Any]
    draft_revision: int
    report_fingerprint: str


class ArchiveAttemptService:
    def __init__(self, database: WorkbenchDatabase, output_root: str | Path) -> None:
        self.database = database
        self.output_root = Path(output_root)
        self.repository = ArchiveAttemptRepository(database)
        self.preparation = ArchivePreparationRepository(database)
        self.sources = SourceRecordRepository(database)
        self.staging_root = self.output_root / "compressed" / ".staging"
        self.staging_root_id = controlled_staging_root_id(
            self.staging_root, database.deployment_instance_id,
        )

    def accept(
        self, case_id: str, source_id: str, source_revision: int,
        context_id: str, expected_case_revision: int, task_id: str | None = None,
    ) -> dict[str, Any]:
        self._require_archive_source(source_id)
        context_id = validate_opaque_id(context_id)
        draft = CaseDraftRepository(self.database).get(case_id)
        result = self.preparation.prepare(
            case_id, source_id, source_revision, context_id, expected_case_revision,
            int(draft["revision"]), report_fingerprint(draft["report"]),
            task_id=task_id,
        )
        if task_id is not None:
            bound = self.repository.get_internal(result["attempt_id"]).get("task_id")
            if bound != task_id:
                raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_BINDING_MISMATCH")
        return result

    def start(self, attempt_id: str) -> dict[str, Any]:
        return self.repository.mark_running(attempt_id)

    def reissue_context(
        self, case_id: str, source_id: str, source_revision: int,
        context_id: str, expected_case_revision: int,
    ) -> dict[str, Any]:
        self._require_archive_source(source_id)
        context_id = validate_opaque_id(context_id)
        draft = CaseDraftRepository(self.database).get(case_id)
        return self.preparation.reissue(
            case_id, source_id, source_revision, context_id, expected_case_revision,
            int(draft["revision"]), report_fingerprint(draft["report"]),
        )

    def context_matches(self, attempt_id: str, context_id: str) -> bool:
        try:
            attempt_id = validate_opaque_id(attempt_id)
            context_id = validate_opaque_id(context_id)
        except WorkbenchPersistenceError:
            return False
        binding = find_binding(self.database, context_id)
        return bool(
            binding and binding["active"]
            and binding["context_kind"] == "workbench"
            and not _expired(binding.get("expires_at"))
            and binding["attempt_id"] == attempt_id
            and binding["attempt_status"] in {"accepted", "running"}
        )

    def context_binding(self, context_id: str) -> dict[str, Any] | None:
        return find_binding(self.database, context_id)

    def succeed(self, attempt_id: str, manifest_id: str) -> dict[str, Any]:
        raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_REQUIRED")

    def workbench_report(
        self, attempt_id: str, context_id: str, client_report: object | None = None,
    ) -> dict[str, Any]:
        binding = find_binding(self.database, context_id)
        if not binding or not binding["active"] or binding["context_kind"] != "workbench":
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_CONTEXT_MISMATCH")
        if binding["attempt_id"] != validate_opaque_id(attempt_id) or _expired(binding.get("expires_at")):
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_CONTEXT_MISMATCH")
        shell = CaseShellRepository(self.database).get(binding["case_id"])
        source = self.sources.get(binding["source_id"])
        draft = CaseDraftRepository(self.database).get(binding["case_id"])
        if (
            shell["source_id"] != binding["source_id"]
            or int(source["revision"]) != binding["source_revision"]
            or source["access_status"] != "available"
            or int(draft["revision"]) != binding["draft_revision"]
            or report_fingerprint(draft["report"]) != binding["report_fingerprint"]
            or shell["lifecycle"] not in {"archive_queued", "archiving"}
        ):
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_BINDING_STALE")
        if client_report is not None and report_fingerprint(client_report) != binding["report_fingerprint"]:
            raise WorkbenchPersistenceError("ARCHIVE_REPORT_MISMATCH")
        return draft["report"]

    def persist_publish_intent(self, attempt_id: str, **kwargs: Any) -> dict[str, Any]:
        from .archive_attempt_completion_service import persist_publish_intent
        return persist_publish_intent(self, attempt_id, **kwargs)

    def revalidate_before_publish(
        self, attempt_id: str, report: object,
    ) -> ArchivePublicationSnapshot:
        attempt = self.repository.get_internal(attempt_id)
        binding = find_active_binding_for_attempt(self.database, attempt_id)
        shell = CaseShellRepository(self.database).get(attempt["case_id"])
        source = self.sources.get(attempt["source_id"])
        draft = CaseDraftRepository(self.database).get(attempt["case_id"])
        if (
            not binding or _expired(binding.get("expires_at"))
            or binding["context_kind"] != "workbench"
            or binding["case_id"] != attempt["case_id"]
            or binding["source_id"] != attempt["source_id"]
            or binding["source_revision"] != int(attempt["source_revision"])
            or binding["draft_revision"] != int(attempt["draft_revision"])
            or binding["report_fingerprint"] != attempt["report_fingerprint"]
            or shell["source_id"] != attempt["source_id"]
            or shell["lifecycle"] not in {"archive_queued", "archiving"}
            or source["access_status"] != "available"
            or int(source["revision"]) != int(attempt["source_revision"])
            or int(draft["revision"]) != int(attempt["draft_revision"])
            or report_fingerprint(draft["report"]) != attempt["report_fingerprint"]
        ):
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_BINDING_STALE")
        return ArchivePublicationSnapshot(
            report=draft["report"],
            draft_revision=int(draft["revision"]),
            report_fingerprint=report_fingerprint(draft["report"]),
        )

    def mark_publish_phase(self, attempt_id: str, phase: str) -> dict[str, Any]:
        from .archive_attempt_completion_service import mark_publish_phase
        return mark_publish_phase(self, attempt_id, phase)

    def complete_verified(
        self, attempt_id: str, registry: Any, manifest_record: Any, *,
        recovery: bool = False, verified_md5s: dict[str, str] | None = None,
        verified_file_identities: dict[str, ArchiveFileIdentity] | None = None,
    ) -> dict[str, Any]:
        from .archive_attempt_completion_service import complete_verified
        return complete_verified(
            self, attempt_id, registry, manifest_record,
            recovery=recovery, verified_md5s=verified_md5s,
            verified_file_identities=verified_file_identities,
        )

    def fail(self, attempt_id: str, error_code: str) -> dict[str, Any]:
        intent = ArchivePublishIntentRepository(self.database).get_for_attempt(attempt_id)
        if intent and intent["phase"] not in {"verified", "conflict"}:
            result = interrupt_attempt(self.database, attempt_id)
            record = self.repository.get_internal(attempt_id)
            if record["staging_locator"]:
                cleanup = cleanup_owned_staging(
                    record, self.staging_root, self.database.deployment_instance_id,
                )
                if cleanup != "not_required":
                    cleanup_error = (
                        "ARCHIVE_STAGING_CLEANUP_UNKNOWN" if cleanup == "unknown" else None
                    )
                    if cleanup == "failed":
                        cleanup_error = "ARCHIVE_STAGING_CLEANUP_FAILED"
                    result = self.repository.mark_cleanup(
                        attempt_id, cleanup, cleanup_error,
                    )
            self._cleanup_execution_input_best_effort(attempt_id)
            return result
        result = self.repository.mark_failed(attempt_id, error_code)
        self.repository.interrupt_case(attempt_id)
        record = self.repository.get_internal(attempt_id)
        if record["staging_locator"]:
            cleanup = cleanup_owned_staging(
                record, self.staging_root, self.database.deployment_instance_id,
            )
            if cleanup != "not_required":
                cleanup_error = (
                    "ARCHIVE_STAGING_CLEANUP_UNKNOWN" if cleanup == "unknown" else None
                )
                if cleanup == "failed":
                    cleanup_error = "ARCHIVE_STAGING_CLEANUP_FAILED"
                result = self.repository.mark_cleanup(attempt_id, cleanup, cleanup_error)
        self._cleanup_execution_input_best_effort(attempt_id)
        return result

    def _cleanup_execution_input_best_effort(self, attempt_id: str) -> None:
        try:
            self.cleanup_execution_input(attempt_id)
        except Exception:
            # 持久快照行保持未密封且可诊断，以便恢复；
            # 绝不能将失败归档变成虚假成功。
            pass

    def staging_initializer(self, attempt_id: str) -> Callable[[Path], None]:
        root_id = self.staging_root_id
        deployment_id = self.database.deployment_instance_id
        task_id = self.repository.get_internal(attempt_id).get("task_id")

        def initialize(staging_dir: Path) -> None:
            token = write_ownership_marker(
                staging_dir, attempt_id, deployment_id, root_id, task_id,
            )
            try:
                self.repository.bind_staging(attempt_id, str(staging_dir), root_id, token)
            except Exception:
                remove_ownership_marker(staging_dir)
                raise

        return initialize

    def process_started_callback(self, attempt_id: str) -> Callable[[int], None]:
        return lambda pid: self.repository.bind_process(attempt_id, pid, utc_now())

    def seal_execution_input(self, attempt_id: str, inventory: Any) -> SealedInputSnapshot:
        return create_sealed_input_snapshot(
            self.database, self.output_root, self.repository.get_internal(attempt_id), inventory,
        )

    def load_execution_input(self, attempt_id: str) -> SealedInputSnapshot:
        return load_sealed_input_snapshot(self.database, self.output_root, attempt_id)

    @staticmethod
    def assert_execution_input(snapshot: SealedInputSnapshot) -> None:
        assert_sealed_input(snapshot)

    def cleanup_execution_input(self, attempt_id: str) -> str:
        return cleanup_sealed_input_snapshot(self.database, self.output_root, attempt_id)

    def remove_marker(self, staging_dir: Path, attempt_id: str | None = None) -> None:
        marker = staging_dir / OWNERSHIP_MARKER_NAME
        attempt_id = attempt_id or self._attempt_for_final_dir(staging_dir)
        if attempt_id is None:
            raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_OWNER_REQUIRED")
        attempt_id = validate_opaque_id(attempt_id)
        intent = ArchivePublishIntentRepository(self.database).get_for_attempt(attempt_id)
        if intent is None:
            raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_INTENT_REQUIRED")
        expected_final = (
            self.output_root / "compressed" / intent["relative_final_dir"]
        ).resolve(strict=False)
        if expected_final != staging_dir.resolve(strict=False) or not staging_dir.is_dir():
            raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_TARGET_MISMATCH")
        fence = (
            get_fence(self.database, str(intent.get("fence_id")))
            if intent.get("fence_id")
            else None
        )
        if (
            fence is None or fence["attempt_id"] != attempt_id
            or fence.get("task_id") != intent.get("task_id")
            or fence.get("deployment_instance_id") != self.database.deployment_instance_id
            or fence["status"] not in {"active", "pending_verification", "consumed"}
            or intent.get("publication_status") not in {"sealed", "published", "verified"}
        ):
            raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_OWNER_REQUIRED")
        if not marker.exists():
            if intent.get("publication_status") in {"published", "verified"}:
                return
            if (
                intent.get("publication_status") == "sealed"
                and validate_published_manifest(SimpleNamespace(
                    public_manifest=intent["public_manifest"], final_dir=staging_dir,
                ))
            ):
                return
            raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_MARKER_MISSING")
        try:
            payload = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_OWNER_REQUIRED") from error
        attempt = self.repository.get_internal(attempt_id)
        expected = {
            "marker_version": 1, "attempt_id": attempt_id,
            "deployment_instance_id": self.database.deployment_instance_id,
            "staging_root_id": attempt.get("staging_root_id"),
            "marker_token": attempt.get("ownership_marker_token"),
        }
        if attempt.get("task_id") is not None:
            expected["task_id"] = attempt.get("task_id")
        if payload != expected:
            raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_OWNER_REQUIRED")
        try:
            remove_ownership_marker(staging_dir)
        except FileNotFoundError:
            if intent.get("publication_status") in {"published", "verified"}:
                return
            if not (
                intent.get("publication_status") == "sealed"
                and validate_published_manifest(SimpleNamespace(
                    public_manifest=intent["public_manifest"], final_dir=staging_dir,
                ))
            ):
                raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_MARKER_MISSING")
        try:
            staging_dir.chmod(
                stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP
                | stat.S_IROTH | stat.S_IXOTH,
            )
        except OSError:
            pass

    def _publish_intent(self, attempt_id: str) -> dict[str, Any] | None:
        from ...repository.archive.archive_publish_intent_repository import ArchivePublishIntentRepository
        return ArchivePublishIntentRepository(self.database).get_for_attempt(attempt_id)

    def _attempt_for_final_dir(self, final_dir: Path) -> str | None:
        try:
            relative = final_dir.resolve(strict=False).relative_to(
                (self.output_root / "compressed").resolve(strict=False),
            ).as_posix()
        except ValueError:
            return None
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT attempt_id FROM archive_publish_intents WHERE relative_final_dir=? "
                "AND deployment_instance_id=? ORDER BY created_at DESC LIMIT 1",
                (relative, self.database.deployment_instance_id),
            ).fetchone()
        return None if row is None else str(row[0])

    def recover_after_restart(self) -> list[str]:
        from .archive_attempt_recovery_reconciliation_service import recover_after_restart
        return recover_after_restart(self)

    def _require_archive_source(self, source_id: str) -> None:
        status = self.sources.get(source_id)["access_status"]
        if status == "pending":
            raise WorkbenchPersistenceError("SOURCE_REVALIDATION_PENDING")
        if status != "available":
            raise WorkbenchPersistenceError("SOURCE_RESELECTION_REQUIRED")
