"""防止私有归档定位符进入 DTO 的投影边界。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def public_attempt(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": int(row["schema_version"]), "attempt_id": str(row["attempt_id"]),
        "case_id": str(row["case_id"]), "source_id": str(row["source_id"]),
        "input_revision": int(row["input_revision"]),
        "status": str(row["status"]), "cleanup_status": str(row["cleanup_status"]),
        "error_code": row["error_code"], "manifest_id": row["manifest_id"],
        "created_at": row["created_at"], "started_at": row["started_at"],
        "finished_at": row["finished_at"], "revision": int(row["revision"]),
    }


def internal_attempt(row: Mapping[str, Any]) -> dict[str, Any]:
    result = public_attempt(row)
    result.update({
        "staging_root_id": row["staging_root_id"], "staging_locator": row["staging_locator"],
        "ownership_marker_token": row["ownership_marker_token"], "process_pid": row["process_pid"],
        "process_started_at": row["process_started_at"],
        "manifest_source_key": row["manifest_source_key"],
        "manifest_input_fingerprint": row["manifest_input_fingerprint"],
        "manifest_archive_fingerprint": row["manifest_archive_fingerprint"],
        "source_revision": int(row["source_revision"] if row["source_revision"] is not None else row["input_revision"]),
        "draft_revision": int(row["draft_revision"] or 0),
        "report_fingerprint": row["report_fingerprint"] or None,
        "task_id": row["task_id"], "deployment_instance_id": row["deployment_instance_id"],
        "input_snapshot_id": row["input_snapshot_id"],
        "input_snapshot_root_id": row["input_snapshot_root_id"],
        "input_snapshot_locator": row["input_snapshot_locator"],
        "input_snapshot_fingerprint": row["input_snapshot_fingerprint"],
        "input_snapshot_status": row["input_snapshot_status"],
    })
    return result
