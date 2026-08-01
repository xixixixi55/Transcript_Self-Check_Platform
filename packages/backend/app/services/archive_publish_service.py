"""Publish a validated staging directory through the workbench evidence boundary."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .archive_attempt_service import ArchiveAttemptService
from .archive_manifest_service import validate_published_manifest
from ..repository.archive_publish_fence_repository import assert_publishable
from ..repository.workbench_errors import WorkbenchPersistenceError


def publish_staged_archive(
    staging_dir: Path, final_dir: Path, record: Any, report: dict[str, Any],
    *, context: Any, attempt_id: str | None, attempt_service: ArchiveAttemptService | None,
    workbench_context_id: str | None,
) -> None:
    if attempt_id is not None and attempt_service is not None:
        attempt_service.revalidate_before_publish(attempt_id, report)
        attempt_service.persist_publish_intent(
            attempt_id,
            source_key=context.source_key,
            input_fingerprint=context.input_fingerprint,
            archive_fingerprint=record.fingerprint,
            manifest_id=record.manifest_id,
            final_dir=final_dir,
            public_manifest=record.public_manifest,
            context_id=workbench_context_id or context.context_id,
            target_context_id=context.context_id,
        )
        # The durable fence is established by persist_publish_intent in the
        # same transaction as the final server-fact validation.  A second
        # ordinary read would not close a TOCTOU window.
        assert_publishable(attempt_service.database, attempt_id)
        if final_dir.exists():
            raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_TARGET_CONFLICT")
    os.replace(staging_dir, final_dir)
    if not validate_published_manifest(record):
        raise ValueError("ARCHIVE_PARTS_INVALID")
    if attempt_id is not None and attempt_service is not None:
        attempt_service.remove_marker(final_dir)
        attempt_service.mark_publish_phase(attempt_id, "published")
    if not validate_published_manifest(record):
        raise ValueError("ARCHIVE_PARTS_INVALID")
