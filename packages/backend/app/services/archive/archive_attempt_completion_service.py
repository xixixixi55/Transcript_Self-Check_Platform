"""归档尝试共享的可信完成与重启协调。"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ...repository.archive_attempt_recovery_repository import (
    complete_verified_attempt,
)
from ...repository.archive_context_binding_repository import report_fingerprint
from ...repository.archive_manifest_repository import ArchiveManifestRepository
from ...repository.archive_publish_intent_repository import ArchivePublishIntentRepository
from ...repository.archive_publish_fence_repository import get as get_fence
from ...repository.case_workbench_repository import CaseDraftRepository, CaseShellRepository
from ...repository.workbench_errors import WorkbenchPersistenceError
from .archive_manifest_service import ArchiveFileIdentity, validate_manifest_files
from .archive_manifest_projection_service import (
    project_verified_manifest_to_legacy_attachments,
)
from .archive_runtime_service import ArchiveManifestRecord
from .archive_publication_identity_service import (
    assert_publication_identity, publication_digest, publication_id,
)


if TYPE_CHECKING:
    from .archive_attempt_service import ArchiveAttemptService


_COMPLETION_MERGE_RETRIES = 3


def persist_publish_intent(
    service: ArchiveAttemptService, attempt_id: str, *, source_key: str,
    input_fingerprint: str, archive_fingerprint: str, manifest_id: str,
    final_dir: Path, public_manifest: dict[str, Any], context_id: str,
    target_context_id: str | None = None,
    publication_id_value: str | None = None,
    expected_draft_revision: int | None = None,
    expected_report_fingerprint: str | None = None,
) -> dict[str, Any]:
    attempt = service.repository.get_internal(attempt_id)
    relative = final_dir.resolve(strict=False).relative_to(
        (service.output_root / "compressed").resolve(strict=False),
    ).as_posix()
    return ArchivePublishIntentRepository(service.database).create(
        attempt_id=attempt_id, case_id=attempt["case_id"], source_id=attempt["source_id"],
        context_id=context_id, target_context_id=target_context_id or context_id,
        source_revision=attempt["source_revision"],
        draft_revision=(attempt["draft_revision"] if expected_draft_revision is None else expected_draft_revision),
        report_fingerprint=(attempt["report_fingerprint"] if expected_report_fingerprint is None else expected_report_fingerprint),
        source_key=source_key,
        input_fingerprint=input_fingerprint, archive_fingerprint=archive_fingerprint,
        manifest_id=manifest_id, relative_final_dir=relative, public_manifest=public_manifest,
        task_id=attempt.get("task_id"),
        deployment_instance_id=attempt.get("deployment_instance_id"),
        publication_id=publication_id_value or publication_id(attempt_id, manifest_id),
    )


def mark_publish_phase(service: ArchiveAttemptService, attempt_id: str, phase: str) -> dict[str, Any]:
    repository = ArchivePublishIntentRepository(service.database)
    intent = repository.get_for_attempt(attempt_id)
    if intent is None:
        raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_INTENT_NOT_FOUND")
    if phase in {"published", "indexed", "verified"} and intent.get("publication_status") in {None, "pending"}:
        final_dir = (service.output_root / "compressed" / intent["relative_final_dir"]).resolve(strict=False)
        record = ArchiveManifestRecord(
            intent["manifest_id"], intent.get("target_context_id", "legacy"),
            intent["archive_fingerprint"], intent["public_manifest"], final_dir,
            0.0, time.time() + 60,
        )
        if validate_manifest_files(record) is not None:
            raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_INVALID")
        digest, file_set = publication_digest(intent, record.public_manifest)
        repository.seal_publication(attempt_id, digest, file_set)
        repository.mark_publication_state(attempt_id, "published")
    return repository.mark_phase(attempt_id, phase)


def complete_verified(
    service: ArchiveAttemptService, attempt_id: str, registry: ArchiveManifestRepository,
    manifest_record: Any, *, recovery: bool = False,
    verified_md5s: dict[str, str] | None = None,
    verified_file_identities: dict[str, ArchiveFileIdentity] | None = None,
) -> dict[str, Any]:
    attempt = service.repository.get_internal(attempt_id)
    manifest_id = _record_value(manifest_record, "manifest_id")
    intent = ArchivePublishIntentRepository(service.database).get_for_attempt(attempt_id)
    if intent is None:
        raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_REQUIRED")
    legacy_task_id = f"legacy-task-{attempt_id}"
    legacy_attempt = (
        attempt.get("task_id") in (None, legacy_task_id)
        and intent.get("task_id") == legacy_task_id
    )
    if (
        (not legacy_attempt and attempt.get("task_id") is None)
        or (not legacy_attempt and intent.get("task_id") != attempt.get("task_id"))
        or intent.get("deployment_instance_id") != service.database.deployment_instance_id
    ):
        raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_CONFLICT")
    if intent["phase"] not in {"indexed", "verified"}:
        raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_REQUIRED")
    if not intent.get("fence_id"):
        raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_FENCE_REQUIRED")
    fence = get_fence(service.database, intent["fence_id"])
    allowed_fence_states = {"pending_verification"} if recovery else {"active"}
    if attempt["status"] == "succeeded":
        allowed_fence_states.update({"consumed", "pending_verification"})
    if (
        fence is None or fence["status"] not in allowed_fence_states
        or fence["attempt_id"] != attempt_id
        or fence["case_id"] != attempt["case_id"]
        or fence["source_id"] != attempt["source_id"]
        or int(fence["source_revision"]) != int(attempt["source_revision"])
        or int(fence["draft_revision"]) != int(attempt["draft_revision"])
        or fence["report_fingerprint"] != attempt["report_fingerprint"]
    ):
        raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_CONFLICT")
    if attempt["status"] == "succeeded":
        if attempt["manifest_id"] != manifest_id:
            raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_CONFLICT")
        return service.repository.get_public(attempt_id)
    if intent.get("publication_status") not in {"sealed", "published", "verified"}:
        raise WorkbenchPersistenceError("ARCHIVE_PUBLICATION_NOT_SEALED")
    expected_digest, expected_file_set = publication_digest(intent, intent["public_manifest"])
    if (
        intent.get("publication_digest") != expected_digest
        or intent.get("publication_file_set") != expected_file_set
    ):
        raise WorkbenchPersistenceError("ARCHIVE_PUBLICATION_IDENTITY_CONFLICT")
    source = service.sources.get(attempt["source_id"])
    shell = CaseShellRepository(service.database).get(attempt["case_id"])
    draft = CaseDraftRepository(service.database).get(attempt["case_id"])
    if (
        shell["source_id"] != attempt["source_id"]
        or shell["lifecycle"] not in ({"archive_interrupted"} if recovery else {"archive_queued", "archiving"})
        or source["access_status"] != "available"
        or int(source["revision"]) != int(attempt["source_revision"])
        or draft["lifecycle"] not in ({"archive_interrupted"} if recovery else {"archive_queued", "archiving"})
    ):
        raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_CONFLICT")
    indexed = next((item for item in registry.find_for_attempt(attempt_id) if item.manifest_id == manifest_id), None)
    if indexed is None:
        raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_REQUIRED")
    try:
        archive_fingerprint = _record_value(manifest_record, "archive_fingerprint")
    except WorkbenchPersistenceError:
        archive_fingerprint = indexed.archive_fingerprint
    record = ArchiveManifestRecord(
        manifest_id, attempt_id, archive_fingerprint, _record_value(manifest_record, "public_manifest"),
        Path(_record_value(manifest_record, "final_dir")),
        float(_record_value(manifest_record, "created_at")), time.time() + 60,
        publication_id=intent.get("publication_id"),
        publication_digest=intent.get("publication_digest"),
    )
    if validate_manifest_files(
        record, verified_md5s=verified_md5s,
        verified_file_identities=verified_file_identities,
    ) is not None:
        registry.mark_invalid(indexed.manifest_id)
        raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_INVALID")
    if (
        indexed.public_manifest != record.public_manifest
        or indexed.archive_fingerprint != record.fingerprint
        or registry.resolve_final_dir(indexed).resolve(strict=False) != record.final_dir.resolve(strict=False)
    ):
        registry.mark_invalid(indexed.manifest_id)
        raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_REQUIRED")
    if any(intent[key] != value for key, value in {
        "manifest_id": indexed.manifest_id, "source_key": indexed.source_key,
        "input_fingerprint": indexed.input_fingerprint,
        "archive_fingerprint": indexed.archive_fingerprint,
        "public_manifest": indexed.public_manifest,
        "case_id": attempt["case_id"], "source_id": attempt["source_id"],
        "source_revision": int(attempt["source_revision"]),
        "draft_revision": int(attempt["draft_revision"]),
        "report_fingerprint": attempt["report_fingerprint"],
    }.items()):
        raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_CONFLICT")
    assert_publication_identity(record, intent)
    expected_final_dir = (service.output_root / "compressed" / intent["relative_final_dir"]).resolve(strict=False)
    if expected_final_dir != record.final_dir.resolve(strict=False):
        raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_TARGET_MISMATCH")
    bound_task_id = attempt.get("task_id") or intent["task_id"]
    evidence = {
        "attempt_id": attempt_id, "manifest_id": record.manifest_id,
        "case_id": attempt["case_id"], "source_id": attempt["source_id"],
        "shell_revision": fence["shell_revision"],
        "source_revision": attempt["source_revision"], "draft_revision": attempt["draft_revision"],
        "report_fingerprint": attempt["report_fingerprint"], "source_key": indexed.source_key,
        "input_fingerprint": indexed.input_fingerprint, "archive_fingerprint": indexed.archive_fingerprint,
        "relative_final_dir": intent["relative_final_dir"], "recovery": recovery,
        "task_id": bound_task_id,
        "deployment_instance_id": service.database.deployment_instance_id,
        "publication_id": intent["publication_id"],
        "publication_digest": intent["publication_digest"],
        "publication_file_set": intent["publication_file_set"],
    }
    result = None
    for merge_attempt in range(_COMPLETION_MERGE_RETRIES):
        latest_shell = CaseShellRepository(service.database).get(attempt["case_id"])
        latest_draft = CaseDraftRepository(service.database).get(attempt["case_id"])
        attachment_projection = project_verified_manifest_to_legacy_attachments(
            latest_draft["report"], record.public_manifest,
        )
        try:
            result = complete_verified_attempt(service.database, {
                **evidence,
                "merge_shell_revision": latest_shell["revision"],
                "merge_draft_revision": latest_draft["revision"],
                "merge_report_fingerprint": report_fingerprint(latest_draft["report"]),
                "attachment_projection": attachment_projection,
            })
            break
        except WorkbenchPersistenceError as error:
            if (
                error.code != "ARCHIVE_COMPLETION_MERGE_CONFLICT"
                or merge_attempt + 1 >= _COMPLETION_MERGE_RETRIES
            ):
                raise
    if result is None:
        raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_MERGE_CONFLICT")
    try:
        service.cleanup_execution_input(attempt_id)
    except Exception:
        # 持久成功状态已经提交；保留密封行供有界清理/恢复流程处理，
        # 不要降级结果。
        pass
    return result


def record_attempt_completion(
    attempt_service: ArchiveAttemptService | None, attempt_id: str | None,
    registry: Any, context: Any, archive_fingerprint: str, manifest_record: Any,
    context_binding_id: str | None = None,
    *, verified_md5s: dict[str, str] | None = None,
    verified_file_identities: dict[str, ArchiveFileIdentity] | None = None,
) -> None:
    if attempt_service is None or attempt_id is None:
        return
    persist_publish_intent(
        attempt_service, attempt_id, source_key=context.source_key,
        input_fingerprint=context.input_fingerprint, archive_fingerprint=archive_fingerprint,
        manifest_id=manifest_record.manifest_id, final_dir=manifest_record.final_dir,
        public_manifest=manifest_record.public_manifest,
        context_id=context_binding_id or context.context_id,
        target_context_id=context.context_id,
        publication_id_value=getattr(manifest_record, "publication_id", None),
    )
    intent = ArchivePublishIntentRepository(attempt_service.database).get_for_attempt(attempt_id)
    if intent is None:
        raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_REQUIRED")
    try:
        if intent["phase"] == "intent_persisted":
            if validate_manifest_files(
                manifest_record, verified_md5s=verified_md5s,
                verified_file_identities=verified_file_identities,
            ) is not None:
                raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_INVALID")
            digest, file_set = publication_digest(intent, manifest_record.public_manifest)
            repository = ArchivePublishIntentRepository(attempt_service.database)
            repository.seal_publication(attempt_id, digest, file_set)
            manifest_record.publication_id = intent["publication_id"]
            manifest_record.publication_digest = digest
            repository.mark_publication_state(attempt_id, "published")
            mark_publish_phase(attempt_service, attempt_id, "published")
            intent = repository.get_for_attempt(attempt_id)
        if getattr(registry, "database", None) is None:
            registry = ArchiveManifestRepository(
                attempt_service.output_root, database=attempt_service.database,
            )
        registry.find_reusable(
            context.source_key, context.input_fingerprint, archive_fingerprint,
            bootstrap_relative=intent["relative_final_dir"],
        )
        registry.save(
            source_key=context.source_key, input_fingerprint=context.input_fingerprint,
            archive_fingerprint=archive_fingerprint, manifest_id=manifest_record.manifest_id,
            final_dir=manifest_record.final_dir, public_manifest=manifest_record.public_manifest,
            created_at=manifest_record.created_at, workbench_attempt_id=attempt_id,
            publication_id=getattr(manifest_record, "publication_id", None),
            publication_digest=getattr(manifest_record, "publication_digest", None),
        )
        if intent is None or intent["phase"] == "published":
            mark_publish_phase(attempt_service, attempt_id, "indexed")
        complete_verified(
            attempt_service, attempt_id, registry, manifest_record,
            verified_md5s=verified_md5s,
            verified_file_identities=verified_file_identities,
        )
    except WorkbenchPersistenceError as error:
        if error.code in {
            "ARCHIVE_COMPLETION_EVIDENCE_CONFLICT", "ARCHIVE_COMPLETION_EVIDENCE_INVALID",
            "ARCHIVE_COMPLETION_EVIDENCE_REQUIRED", "ARCHIVE_PUBLISH_TARGET_MISMATCH",
        }:
            registry.mark_invalid(manifest_record.manifest_id)
        raise


def _record_value(record: Any, name: str) -> Any:
    value = getattr(record, name, None)
    if value is not None:
        return value
    if isinstance(record, dict) and name in record:
        return record[name]
    raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_REQUIRED")
