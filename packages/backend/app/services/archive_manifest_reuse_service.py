"""Restore an independently registered, still-valid archive Manifest."""

from __future__ import annotations

import time

from .archive_manifest_service import validate_manifest_files
from .archive_runtime_service import (
    ARCHIVE_MANIFEST_TTL_SECONDS,
    ARCHIVE_RUNTIME_STORE,
    ArchiveManifestRecord,
)


def restore_persisted_manifest(context, fingerprint: str, registry):
    for persisted in registry.find_reusable(
        context.source_key, context.input_fingerprint, fingerprint,
    ):
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
