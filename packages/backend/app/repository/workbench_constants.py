"""Versioned persistence constants mirrored from the SharedTypes contract."""

from __future__ import annotations

WORKBENCH_SCHEMA_VERSION = 1
WORKBENCH_DATABASE_SCHEMA_VERSION = 2
WORKBENCH_API_VERSION = "v1"
DEFAULT_RETENTION_DAYS = 30
RETENTION_CONFIG_KEY = "workbench.successful_case_retention_days"
LEASE_HEARTBEAT_SECONDS = 15
LEASE_TIMEOUT_SECONDS = 120
MAX_RUNNING_ARCHIVE_TASKS = 6
MAX_CASE_DTO_BYTES = 2 * 1024 * 1024
MAX_CASE_IMAGE_BYTES = 10 * 1024 * 1024
MAX_CASE_IMAGE_COUNT = 200
MAX_CASE_IMAGE_TOTAL_BYTES = 1024 * 1024 * 1024
ASSET_ORPHAN_RETENTION_SECONDS = 60 * 60

CASE_LIFECYCLES = {
    "case_created", "parse_queued", "parsing", "review_ready",
    "parse_failed_retryable", "archive_deferred", "archive_interrupted", "archive_queued",
    "archiving", "archive_verified", "exporting_word", "exported",
    "record_retention_expired", "record_cleaned", "cancelling", "cancelled",
}
REVIEWABLE_LIFECYCLES = {
    "review_ready", "archive_deferred", "archive_interrupted", "archive_queued", "archiving",
    "archive_verified", "exporting_word", "exported",
}
CASE_TRANSITIONS = {
    "case_created": {"parse_queued", "cancelling"},
    "parse_queued": {"parsing", "parse_failed_retryable", "cancelling"},
    "parsing": {"review_ready", "parse_failed_retryable", "cancelling"},
    "review_ready": {"archive_deferred", "archive_queued", "exporting_word", "cancelling"},
    "parse_failed_retryable": {"parse_queued", "cancelling"},
    "archive_deferred": {"archive_queued", "exporting_word", "cancelling"},
    "archive_interrupted": {"archive_deferred", "archive_queued", "cancelling"},
    "archive_queued": {"archiving", "archive_interrupted", "cancelling"},
    "archiving": {"archive_verified", "archive_deferred", "archive_interrupted", "cancelling"},
    "archive_verified": {"exporting_word", "cancelling"},
    "exporting_word": {"exported", "archive_verified", "cancelling"},
    "exported": {"record_retention_expired"},
    "record_retention_expired": {"record_cleaned"},
    "record_cleaned": set(),
    "cancelling": {"cancelled"},
    "cancelled": {"parse_queued", "archive_queued"},
}
TASK_KINDS = {"parse", "archive", "export_word", "cleanup"}
TASK_STATUSES = {
    "queued", "running", "cancelling", "interrupted", "succeeded",
    "failed_retryable", "failed_terminal", "cancelled", "blocked",
}
TASK_TRANSITIONS = {
    "queued": {"running", "cancelling", "cancelled", "blocked"},
    "running": {"cancelling", "succeeded", "failed_retryable", "failed_terminal", "interrupted"},
    "cancelling": {"cancelled", "interrupted", "failed_retryable"},
    "interrupted": {"queued", "failed_retryable", "cancelled"},
    "failed_retryable": {"queued", "running", "cancelled"},
    "blocked": {"queued", "cancelling", "failed_terminal"},
    "succeeded": set(),
    "failed_terminal": set(),
    "cancelled": set(),
}
TASK_STAGES = {
    "parse", "inventory", "planning", "winrar", "integrity", "md5",
    "manifest", "export", "cleanup", "none",
}
SOURCE_ACCESS_STATUSES = {"pending", "available", "invalid", "requires_reselection"}
SOURCE_TYPES = {"report_directory", "report_archive", "uploaded_file", "other"}
LEASE_STATUSES = {"active", "released", "expired"}
ARCHIVE_ATTEMPT_STATUSES = {"accepted", "running", "succeeded", "failed", "interrupted"}
ARCHIVE_CLEANUP_STATUSES = {"not_required", "pending", "succeeded", "failed", "unknown"}
