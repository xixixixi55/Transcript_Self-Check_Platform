"""Safe archive-task card projection with verified-Manifest completion fencing."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .workbench_constants import ARCHIVE_WORKFLOW_MILESTONES
from .workbench_database import WorkbenchDatabase

_ERROR_STATES = {"interrupted", "failed_retryable", "failed_terminal", "cancelled", "blocked"}
_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|/(?:Users|home|tmp|var|etc|opt)/)[^\s,;)]*", re.I)
_TRACE = re.compile(r"^\s*(?:at\s|traceback|file\s+\".*\",\s+line\s+\d+)", re.I)


def build_archive_task_card_summary(
    database: WorkbenchDatabase, task: Mapping[str, Any],
) -> dict[str, Any]:
    summary = {
        key: task[key] for key in (
            "task_id", "case_id", "status", "progress_kind", "stage", "stage_label",
            "stage_index", "stage_count", "percent", "started_at", "updated_at",
            "finished_at", "last_heartbeat_at", "output_bytes", "output_volume_count",
            "last_output_change_at", "worker_state", "allowed_actions",
        )
    }
    summary["error_summary"] = (
        safe_error(task.get("error_summary")) if task["status"] in _ERROR_STATES else None
    )
    if task["status"] == "succeeded" and not _has_verified_manifest(database, task):
        stage_index = list(ARCHIVE_WORKFLOW_MILESTONES).index("manifest") + 1
        summary.update({
            "status": "interrupted",
            "stage": "manifest",
            "stage_label": ARCHIVE_WORKFLOW_MILESTONES["manifest"][1],
            "stage_index": stage_index,
            "percent": ARCHIVE_WORKFLOW_MILESTONES["manifest"][0],
            "worker_state": "released",
            "allowed_actions": ["view_details"],
            "error_summary": "归档结果尚未通过 Manifest 验证。",
        })
    return summary


def _has_verified_manifest(
    database: WorkbenchDatabase, task: Mapping[str, Any],
) -> bool:
    attempt_id = (task.get("process_binding") or {}).get("staging_asset_id")
    if not attempt_id:
        return False
    with database.connect() as connection:
        row = connection.execute(
            "SELECT status,manifest_id FROM archive_attempts WHERE attempt_id=?",
            (attempt_id,),
        ).fetchone()
    return bool(row and row["status"] == "succeeded" and row["manifest_id"])


def safe_error(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    lines = [line for line in value.splitlines() if not _TRACE.search(line)]
    compact = re.sub(
        r"\s+", " ", _PATH.sub("[local path redacted]", " ".join(lines)),
    ).strip()
    return compact if len(compact) <= 160 else f"{compact[:159]}\u2026"
