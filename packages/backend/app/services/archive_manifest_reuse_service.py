"""Restore an independently registered, still-valid archive Manifest."""

from __future__ import annotations

import time

from ..repository.archive_publish_intent_repository import ArchivePublishIntentRepository
from .archive_manifest_service import validate_manifest_files
from .archive_runtime_service import (
    ARCHIVE_MANIFEST_TTL_SECONDS,
    ARCHIVE_RUNTIME_STORE,
    ArchiveManifestRecord,
)


def restore_persisted_manifest(
    context, fingerprint: str, registry, *, attempt_service=None, attempt_id: str | None = None,
):
    for persisted in registry.find_reusable(
        context.source_key, context.input_fingerprint, fingerprint,
    ):
        if persisted.workbench_attempt_id is not None:
            if attempt_service is None or persisted.workbench_attempt_id != attempt_id:
                continue
            intent = ArchivePublishIntentRepository(attempt_service.database).get_for_attempt(
                persisted.workbench_attempt_id,
            )
            if intent is None or intent["phase"] != "verified" or any(
                intent[key] != value for key, value in {
                    "manifest_id": persisted.manifest_id,
                    "source_key": persisted.source_key,
                    "input_fingerprint": persisted.input_fingerprint,
                    "archive_fingerprint": persisted.archive_fingerprint,
                    "relative_final_dir": persisted.relative_final_dir,
                    "public_manifest": persisted.public_manifest,
                }.items()
            ):
                continue
        record = ArchiveManifestRecord(
            persisted.manifest_id, context.context_id, fingerprint,
            persisted.public_manifest, registry.resolve_final_dir(persisted),
            persisted.created_at, time.time() + ARCHIVE_MANIFEST_TTL_SECONDS,
        )
        if validate_manifest_files(record) is not None:
            registry.mark_invalid(persisted.manifest_id)
            continue
        attached = ARCHIVE_RUNTIME_STORE.attach_manifest(context.context_id, record)
        registry.touch(persisted.manifest_id)
        return attached
    return None
