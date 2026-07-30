"""TaskRecord persistence with optimistic revisions and legacy defaults."""
from __future__ import annotations
from collections.abc import Mapping
from typing import Any

from .workbench_constants import (
    ARCHIVE_TASK_ACTIONS,
    ARCHIVE_WORKER_STATES,
    ARCHIVE_WORKFLOW_MILESTONES,
    TASK_KINDS,
    TASK_STAGES,
    TASK_STATUSES,
    TASK_TRANSITIONS,
)
from .workbench_database import WorkbenchDatabase, normalize_optional_utc, normalize_utc, utc_now
from .workbench_errors import RevisionConflictError, WorkbenchPersistenceError
from .workbench_repository_helpers import bool_int, json_text, row_json
from .workbench_serialization import validate_opaque_id, validate_safe_string

_UPDATE_FIELDS = {
    "status", "stage", "percent", "counters", "process_binding", "error_code",
    "error_summary", "cancel_requested", "started_at", "updated_at", "finished_at",
    "attempt", "progress_kind", "stage_label", "stage_index", "stage_count",
    "last_heartbeat_at", "output_bytes", "output_volume_count",
    "last_output_change_at", "worker_state", "allowed_actions",
}
class TaskRecordRepository:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database

    def create(self, task: Mapping[str, Any]) -> dict[str, Any]:
        value = _normalized_task(task)
        columns = (
            "task_id, schema_version, case_id, kind, status, stage, percent, counters_json, "
            "input_revision, attempt, process_binding_json, error_code, error_summary, "
            "cancel_requested, created_at, started_at, updated_at, finished_at, progress_kind, "
            "stage_label, stage_index, stage_count, last_heartbeat_at, output_bytes, "
            "output_volume_count, last_output_change_at, worker_state, allowed_actions_json, revision"
        )
        values = (
            value["task_id"], 1, value["case_id"], value["kind"], value["status"],
            value["stage"], value["percent"], json_text(value["counters"]),
            value["input_revision"], value["attempt"],
            None if value["process_binding"] is None else json_text(value["process_binding"]),
            value["error_code"], value["error_summary"], bool_int(value["cancel_requested"]),
            value["created_at"], value["started_at"], value["updated_at"], value["finished_at"],
            value["progress_kind"], value["stage_label"], value["stage_index"],
            value["stage_count"], value["last_heartbeat_at"], value["output_bytes"],
            value["output_volume_count"], value["last_output_change_at"], value["worker_state"],
            json_text(value["allowed_actions"]), 0,
        )
        with self.database.transaction() as connection:
            try:
                connection.execute(
                    f"INSERT INTO task_records({columns}) VALUES ({','.join('?' for _ in values)})",
                    values,
                )
            except Exception as error:
                raise WorkbenchPersistenceError("TASK_CREATE_FAILED") from error
        return self.get(value["task_id"])

    def get(self, task_id: str) -> dict[str, Any]:
        task_id = validate_opaque_id(task_id)
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM task_records WHERE task_id = ?", (task_id,)
            ).fetchone()
        if row is None:
            raise WorkbenchPersistenceError("TASK_NOT_FOUND")
        return _task_dict(row)

    def update(
        self, task_id: str, changes: Mapping[str, Any], expected_revision: int
    ) -> dict[str, Any]:
        if any(key not in _UPDATE_FIELDS for key in changes):
            raise WorkbenchPersistenceError("INVALID_TASK_UPDATE")
        current = self.get(task_id)
        if current["revision"] != expected_revision:
            raise RevisionConflictError("task", expected_revision, current["revision"])
        next_value = _normalized_task({**current, **changes}, existing=True)
        if (
            next_value["status"] != current["status"]
            and next_value["status"] not in TASK_TRANSITIONS[current["status"]]
        ):
            raise WorkbenchPersistenceError("INVALID_TASK_TRANSITION")
        assignments = (
            "status=?, stage=?, percent=?, counters_json=?, process_binding_json=?, "
            "error_code=?, error_summary=?, cancel_requested=?, attempt=?, started_at=?, "
            "updated_at=?, finished_at=?, progress_kind=?, stage_label=?, stage_index=?, "
            "stage_count=?, last_heartbeat_at=?, output_bytes=?, output_volume_count=?, "
            "last_output_change_at=?, worker_state=?, allowed_actions_json=?, revision=revision+1"
        )
        values = (
            next_value["status"], next_value["stage"], next_value["percent"],
            json_text(next_value["counters"]),
            None if next_value["process_binding"] is None else json_text(next_value["process_binding"]),
            next_value["error_code"], next_value["error_summary"],
            bool_int(next_value["cancel_requested"]), next_value["attempt"],
            next_value["started_at"], next_value["updated_at"], next_value["finished_at"],
            next_value["progress_kind"], next_value["stage_label"], next_value["stage_index"],
            next_value["stage_count"], next_value["last_heartbeat_at"],
            next_value["output_bytes"], next_value["output_volume_count"],
            next_value["last_output_change_at"], next_value["worker_state"],
            json_text(next_value["allowed_actions"]), task_id, expected_revision,
        )
        with self.database.transaction() as connection:
            updated = connection.execute(
                f"UPDATE task_records SET {assignments} WHERE task_id=? AND revision=?", values
            )
            if updated.rowcount != 1:
                actual = self.get(task_id)["revision"]
                raise RevisionConflictError("task", expected_revision, actual)
        return self.get(task_id)

    def mark_running_tasks_interrupted(self) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT task_id FROM task_records WHERE status IN ('running','cancelling')"
            ).fetchall()
        results = []
        for row in rows:
            task = self.get(str(row[0]))
            results.append(self.update(str(row[0]), {
                "status": "interrupted",
                "error_code": "TASK_RESTART_INTERRUPTED",
                "error_summary": "TASK_RESTART_INTERRUPTED",
                "worker_state": "waiting_reclaim" if task["kind"] == "archive" else None,
                "allowed_actions": ARCHIVE_TASK_ACTIONS["interrupted"]
                if task["kind"] == "archive" else [],
                "updated_at": utc_now(),
            }, task["revision"]))
        return results


def _normalized_task(task: Mapping[str, Any], *, existing: bool = False) -> dict[str, Any]:
    result = dict(task)
    result["task_id"] = validate_opaque_id(task.get("task_id"))
    result["case_id"] = validate_opaque_id(task.get("case_id"))
    result["kind"] = str(task.get("kind", "parse"))
    result["status"] = str(task.get("status", "queued"))
    result["stage"] = str(task.get("stage", "parse"))
    if result["kind"] not in TASK_KINDS or result["status"] not in TASK_STATUSES or result["stage"] not in TASK_STAGES:
        raise WorkbenchPersistenceError("INVALID_TASK_RECORD")
    _validate_progress(result.get("percent"))
    result["percent"] = task.get("percent")
    result["counters"] = _counter_map(task.get("counters", {}))
    result["input_revision"] = _non_negative_int(task.get("input_revision", 0))
    result["attempt"] = _non_negative_int(task.get("attempt", 0))
    result["process_binding"] = _process_binding(task.get("process_binding"))
    _validate_error_fields(task.get("error_code"), task.get("error_summary"))
    result["error_code"] = task.get("error_code")
    result["error_summary"] = task.get("error_summary")
    result["cancel_requested"] = bool(task.get("cancel_requested", False))
    result["created_at"] = normalize_utc(task.get("created_at"))
    result["started_at"] = normalize_optional_utc(task.get("started_at"))
    result["finished_at"] = normalize_optional_utc(task.get("finished_at"))
    result["updated_at"] = normalize_utc(task.get("updated_at") if existing else task.get("updated_at"))
    for key in ("last_heartbeat_at", "last_output_change_at"):
        result[key] = normalize_optional_utc(task.get(key))
    for key in ("output_bytes", "output_volume_count", "stage_index", "stage_count"):
        result[key] = None if task.get(key) is None else _non_negative_int(task[key])
    result["progress_kind"] = task.get("progress_kind")
    result["stage_label"] = task.get("stage_label")
    worker_state = task.get("worker_state")
    if worker_state is not None and worker_state not in ARCHIVE_WORKER_STATES:
        raise WorkbenchPersistenceError("INVALID_TASK_RECORD")
    result["worker_state"] = worker_state
    actions = task.get("allowed_actions", ARCHIVE_TASK_ACTIONS.get(result["status"], []))
    if not isinstance(actions, list) or any(action not in {"cancel", "retry", "view_result", "view_details"} for action in actions):
        raise WorkbenchPersistenceError("INVALID_TASK_RECORD")
    result["allowed_actions"] = list(actions)
    return result


def _task_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    keys = set(row.keys())
    value = {key: row[key] if key in keys else None for key in (
        "updated_at", "progress_kind", "stage_label", "stage_index", "stage_count",
        "last_heartbeat_at", "output_bytes", "output_volume_count",
        "last_output_change_at", "worker_state", "allowed_actions_json",
    )}
    status, kind, stage = str(row["status"]), str(row["kind"]), str(row["stage"])
    milestone = ARCHIVE_WORKFLOW_MILESTONES.get(stage)
    legacy_archive = kind == "archive" and value["progress_kind"] is None
    worker_state = value["worker_state"]
    if kind == "archive" and worker_state is None:
        worker_state = "waiting_reclaim" if status in {"running", "cancelling", "interrupted"} else (
            "released" if status in {"succeeded", "failed_retryable", "failed_terminal", "cancelled"} else "unassigned"
        )
    return {
        "schema_version": int(row["schema_version"]), "task_id": row["task_id"],
        "case_id": row["case_id"], "kind": kind, "status": status, "stage": stage,
        "percent": row["percent"], "counters": row_json(row, "counters_json"),
        "input_revision": int(row["input_revision"]), "attempt": int(row["attempt"]),
        "process_binding": None if row["process_binding_json"] is None else row_json(row, "process_binding_json"),
        "error_code": row["error_code"], "error_summary": row["error_summary"],
        "cancel_requested": bool(row["cancel_requested"]), "created_at": row["created_at"],
        "started_at": row["started_at"], "updated_at": value["updated_at"] or row["finished_at"] or row["started_at"] or row["created_at"],
        "finished_at": row["finished_at"],
        "progress_kind": "workflow_milestone" if legacy_archive else value["progress_kind"],
        "stage_label": value["stage_label"] or (milestone[1] if milestone else None),
        "stage_index": value["stage_index"] or (
            list(ARCHIVE_WORKFLOW_MILESTONES).index(stage) + 1 if milestone else None
        ),
        "stage_count": value["stage_count"] or (
            len(ARCHIVE_WORKFLOW_MILESTONES) if milestone else None
        ),
        "last_heartbeat_at": value["last_heartbeat_at"], "output_bytes": value["output_bytes"],
        "output_volume_count": value["output_volume_count"],
        "last_output_change_at": value["last_output_change_at"], "worker_state": worker_state,
        "allowed_actions": ARCHIVE_TASK_ACTIONS.get(status, []) if legacy_archive
        else (row_json(row, "allowed_actions_json") if value["allowed_actions_json"] else []),
        "revision": int(row["revision"]),
    }


def _validate_progress(value: Any) -> None:
    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100):
        raise WorkbenchPersistenceError("INVALID_TASK_PROGRESS")


def _counter_map(value: Any) -> dict[str, int | float]:
    if not isinstance(value, Mapping) or any(not isinstance(k, str) or isinstance(v, bool) or not isinstance(v, (int, float)) for k, v in value.items()):
        raise WorkbenchPersistenceError("INVALID_TASK_PROGRESS")
    return dict(value)


def _process_binding(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) - {"process_tree_id", "staging_asset_id"}:
        raise WorkbenchPersistenceError("INVALID_TASK_RECORD")
    validate_opaque_id(value.get("process_tree_id"))
    if value.get("staging_asset_id") is not None:
        validate_opaque_id(value.get("staging_asset_id"))
    return dict(value)


def _validate_error_fields(code: Any, summary: Any) -> None:
    if code is not None:
        validate_safe_string(code, "INVALID_TASK_RECORD")
    if summary is not None:
        validate_safe_string(summary, "INVALID_TASK_RECORD")


def _non_negative_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise WorkbenchPersistenceError("INVALID_TASK_RECORD")
    return value
