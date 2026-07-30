"""Archive task state, selection, restart projection, and safe card summaries."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from .task_record_repository import TaskRecordRepository
from .workbench_constants import ARCHIVE_TASK_ACTIONS, ARCHIVE_WORKFLOW_MILESTONES
from .workbench_database import WorkbenchDatabase, utc_now
from .workbench_errors import WorkbenchPersistenceError
from .workbench_serialization import validate_opaque_id

_ACTIVE = ("queued", "running", "cancelling", "blocked")
_ERROR_STATES = {"interrupted", "failed_retryable", "failed_terminal", "cancelled", "blocked"}
_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|/(?:Users|home|tmp|var|etc|opt)/)[^\s,;)]*", re.I)
_TRACE = re.compile(r"^\s*(?:at\s|traceback|file\s+\".*\",\s+line\s+\d+)", re.I)


class ArchiveTaskRepository:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database
        self.tasks = TaskRecordRepository(database)

    def create(self, task: Mapping[str, Any]) -> dict[str, Any]:
        stage = str(task.get("stage", "queued"))
        milestone = _milestone(stage)
        status = str(task.get("status", "queued"))
        value = {
            **task, "kind": "archive", "status": status, "stage": stage,
            "percent": task.get("percent", milestone[0]),
            "progress_kind": "workflow_milestone", "stage_label": milestone[1],
            "stage_index": _stage_index(stage),
            "stage_count": len(ARCHIVE_WORKFLOW_MILESTONES),
            "worker_state": task.get("worker_state", "unassigned"),
            "allowed_actions": ARCHIVE_TASK_ACTIONS[status],
        }
        _validate_milestone(value)
        return self.tasks.create(value)

    def get(self, task_id: str) -> dict[str, Any]:
        task = self.tasks.get(task_id)
        if task["kind"] != "archive":
            raise WorkbenchPersistenceError("ARCHIVE_TASK_NOT_FOUND")
        return task

    def update_state(
        self, task_id: str, changes: Mapping[str, Any], expected_revision: int
    ) -> dict[str, Any]:
        current = self.get(task_id)
        stage = str(changes.get("stage", current["stage"]))
        milestone = _milestone(stage)
        status = str(changes.get("status", current["status"]))
        value = {
            **changes, "stage": stage, "percent": changes.get("percent", milestone[0]),
            "progress_kind": "workflow_milestone", "stage_label": milestone[1],
            "stage_index": _stage_index(stage),
            "stage_count": len(ARCHIVE_WORKFLOW_MILESTONES),
            "allowed_actions": ARCHIVE_TASK_ACTIONS[status],
            "updated_at": changes.get("updated_at", utc_now()),
        }
        if "error_summary" in value:
            value["error_summary"] = _safe_error(value["error_summary"])
        _validate_milestone({**current, **value})
        if _stage_index(stage) < _stage_index(current["stage"]):
            raise WorkbenchPersistenceError("ARCHIVE_STAGE_REGRESSION")
        if status in {"succeeded", "failed_retryable", "failed_terminal", "cancelled"}:
            value.setdefault("finished_at", value["updated_at"])
            value.setdefault("worker_state", "released")
        return self.tasks.update(task_id, value, expected_revision)

    def get_current_or_recent(self, case_id: str) -> dict[str, Any] | None:
        case_id = validate_opaque_id(case_id)
        placeholders = ",".join("?" for _ in _ACTIVE)
        with self.database.connect() as connection:
            row = connection.execute(
                f"SELECT task_id FROM task_records WHERE case_id=? AND kind='archive' "
                f"AND status IN ({placeholders}) ORDER BY updated_at DESC, created_at DESC LIMIT 1",
                (case_id, *_ACTIVE),
            ).fetchone()
            if row is None:
                row = connection.execute(
                    "SELECT task_id FROM task_records WHERE case_id=? AND kind='archive' "
                    "AND status NOT IN ('queued','running','cancelling','blocked') "
                    "ORDER BY COALESCE(finished_at,updated_at,created_at) DESC LIMIT 1",
                    (case_id,),
                ).fetchone()
        return None if row is None else self.get(str(row[0]))

    def get_history(self, case_id: str) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT task_id FROM task_records WHERE case_id=? AND kind='archive' "
                "ORDER BY created_at DESC, task_id DESC", (validate_opaque_id(case_id),)
            ).fetchall()
        return [self.get(str(row[0])) for row in rows]

    def recover_after_restart(self) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT task_id FROM task_records WHERE kind='archive' "
                "AND status IN ('running','cancelling')"
            ).fetchall()
        recovered = []
        for row in rows:
            task = self.get(str(row[0]))
            recovered.append(self.update_state(task["task_id"], {
                "status": "interrupted", "worker_state": "waiting_reclaim",
                "error_code": "ARCHIVE_WAITING_RECLAIM",
                "error_summary": "Archive task is waiting for safe reclaim.",
            }, task["revision"]))
        return recovered

    def get_card_summary(self, case_id: str) -> dict[str, Any] | None:
        task = self.get_current_or_recent(case_id)
        if task is None:
            return None
        summary = {
            key: task[key] for key in (
                "task_id", "case_id", "status", "progress_kind", "stage", "stage_label",
                "stage_index", "stage_count", "percent", "started_at", "updated_at",
                "finished_at", "last_heartbeat_at", "output_bytes", "output_volume_count",
                "last_output_change_at", "worker_state", "allowed_actions",
            )
        }
        summary["error_summary"] = (
            _safe_error(task.get("error_summary")) if task["status"] in _ERROR_STATES else None
        )
        return summary


def _milestone(stage: str) -> tuple[int, str]:
    try:
        return ARCHIVE_WORKFLOW_MILESTONES[stage]
    except KeyError as error:
        raise WorkbenchPersistenceError("INVALID_ARCHIVE_STAGE") from error


def _stage_index(stage: str) -> int:
    return list(ARCHIVE_WORKFLOW_MILESTONES).index(stage) + 1


def _validate_milestone(task: Mapping[str, Any]) -> None:
    if task.get("progress_kind") != "workflow_milestone":
        raise WorkbenchPersistenceError("INVALID_TASK_PROGRESS")
    if task.get("percent") != _milestone(str(task.get("stage")))[0]:
        raise WorkbenchPersistenceError("INVALID_TASK_PROGRESS")


def _safe_error(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    lines = [line for line in value.splitlines() if not _TRACE.search(line)]
    compact = re.sub(r"\s+", " ", _PATH.sub("[local path redacted]", " ".join(lines))).strip()
    return compact if len(compact) <= 160 else f"{compact[:159]}\u2026"
