"""Record the durable publication/index/completion sequence for an attempt."""

from __future__ import annotations

from typing import Any

from ..repository.archive_manifest_repository import ArchiveManifestRepository
from ..repository.archive_publish_intent_repository import ArchivePublishIntentRepository
from ..repository.workbench_errors import WorkbenchPersistenceError
from .archive_manifest_service import ArchiveFileIdentity, validate_manifest_files
from .archive_publication_identity_service import publication_digest


def record_attempt_completion(
    attempt_service: Any, attempt_id: str | None, registry: Any, context: Any,
    archive_fingerprint: str, manifest_record: Any,
    context_binding_id: str | None = None,
    *, verified_md5s: dict[str, str] | None = None,
    verified_file_identities: dict[str, ArchiveFileIdentity] | None = None,
) -> None:
    if attempt_service is None or attempt_id is None:
        return
    from .archive_attempt_completion_service import (
        complete_verified, mark_publish_phase, persist_publish_intent,
    )
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
