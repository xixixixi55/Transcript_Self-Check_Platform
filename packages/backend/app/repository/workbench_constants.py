"""Versioned persistence constants mirrored from the SharedTypes contract."""

from __future__ import annotations

WORKBENCH_SCHEMA_VERSION = 1
WORKBENCH_DATABASE_SCHEMA_VERSION = 6
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
ARCHIVE_ACTIVITY_PERSIST_INTERVAL_SECONDS = 15

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
    "queued", "parse", "inventory", "planning", "preflight_verified", "winrar",
    "integrity", "integrity_verified", "md5", "manifest", "completed",
    "export", "cleanup", "none",
}
ARCHIVE_WORKFLOW_MILESTONES = {
    "queued": (0, "\u7b49\u5f85\u5f52\u6863\u6216\u8d44\u6e90\u51c6\u5165"),
    "inventory": (10, "\u6b63\u5728\u6838\u5bf9\u6587\u4ef6\u6e05\u5355\u4e0e\u8def\u5f84"),
    "preflight_verified": (20, "\u5f52\u6863\u524d\u7f6e\u68c0\u67e5\u901a\u8fc7"),
    "winrar": (30, "\u6b63\u5728\u521b\u5efa RAR \u5206\u5377"),
    "integrity": (75, "RAR \u5206\u5377\u521b\u5efa\u5b8c\u6210\uff0c\u6b63\u5728\u6821\u9a8c"),
    "integrity_verified": (85, "\u5206\u5377\u5b8c\u6574\u6027\u6821\u9a8c\u901a\u8fc7"),
    "md5": (90, "\u6b63\u5728\u8ba1\u7b97 MD5"),
    "manifest": (95, "\u6b63\u5728\u5199\u5165\u5e76\u9a8c\u8bc1 Manifest"),
    "completed": (100, "\u5f52\u6863\u5b8c\u6210"),
}
ARCHIVE_WORKER_STATES = {
    "unassigned", "starting", "owned_running", "recovering", "waiting_reclaim", "released",
}
ARCHIVE_TASK_ACTIONS = {
    "queued": ["cancel"], "running": ["cancel"], "cancelling": [],
    "interrupted": ["view_details", "retry"], "succeeded": ["view_result"],
    "failed_retryable": ["view_details", "retry"], "failed_terminal": ["view_details"],
    "cancelled": ["view_details", "retry"], "blocked": ["view_details", "cancel"],
}
SOURCE_ACCESS_STATUSES = {"pending", "available", "invalid", "requires_reselection"}
SOURCE_TYPES = {"report_directory", "report_archive", "uploaded_file", "other"}
LEASE_STATUSES = {"active", "released", "expired"}
ARCHIVE_ATTEMPT_STATUSES = {"accepted", "running", "succeeded", "failed", "interrupted"}
ARCHIVE_CLEANUP_STATUSES = {"not_required", "pending", "succeeded", "failed", "unknown"}
