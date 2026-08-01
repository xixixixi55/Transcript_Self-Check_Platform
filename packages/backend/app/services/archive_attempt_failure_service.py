"""Failure transition and owned-resource cleanup for archive attempts."""

from __future__ import annotations

from typing import Any

from ..repository.archive_attempt_restart_repository import interrupt_attempt
from ..repository.archive_publish_intent_repository import ArchivePublishIntentRepository
from .archive_staging_security_service import cleanup_owned_staging


def fail_attempt(service: Any, attempt_id: str, error_code: str) -> dict[str, Any]:
    intent = ArchivePublishIntentRepository(service.database).get_for_attempt(attempt_id)
    if intent and intent["phase"] not in {"verified", "conflict"}:
        result = interrupt_attempt(service.database, attempt_id)
        record = service.repository.get_internal(attempt_id)
        if record["staging_locator"]:
            cleanup = cleanup_owned_staging(
                record, service.staging_root, service.database.deployment_instance_id,
            )
            if cleanup != "not_required":
                cleanup_error = "ARCHIVE_STAGING_CLEANUP_UNKNOWN" if cleanup == "unknown" else None
                if cleanup == "failed":
                    cleanup_error = "ARCHIVE_STAGING_CLEANUP_FAILED"
                result = service.repository.mark_cleanup(attempt_id, cleanup, cleanup_error)
        service._cleanup_execution_input_best_effort(attempt_id)
        return result
    result = service.repository.mark_failed(attempt_id, error_code)
    service.repository.interrupt_case(attempt_id)
    record = service.repository.get_internal(attempt_id)
    if record["staging_locator"]:
        cleanup = cleanup_owned_staging(
            record, service.staging_root, service.database.deployment_instance_id,
        )
        if cleanup != "not_required":
            cleanup_error = "ARCHIVE_STAGING_CLEANUP_UNKNOWN" if cleanup == "unknown" else None
            if cleanup == "failed":
                cleanup_error = "ARCHIVE_STAGING_CLEANUP_FAILED"
            result = service.repository.mark_cleanup(attempt_id, cleanup, cleanup_error)
    service._cleanup_execution_input_best_effort(attempt_id)
    return result
