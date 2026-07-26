"""TaskRecord persistence and conservative restart handling."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .workbench_constants import TASK_KINDS, TASK_STAGES, TASK_STATUSES, TASK_TRANSITIONS
from .workbench_database import WorkbenchDatabase, normalize_optional_utc, normalize_utc, utc_now
from .workbench_errors import RevisionConflictError, WorkbenchPersistenceError
from .workbench_repository_helpers import bool_int, json_text, row_json
from .workbench_serialization import validate_opaque_id, validate_safe_string


class TaskRecordRepository:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database

    def create(self, task: Mapping[str, Any]) -> dict[str, Any]:
        task_id = validate_opaque_id(task.get("task_id"))
        case_id = validate_opaque_id(task.get("case_id"))
        kind = str(task.get("kind", "parse"))
        status = str(task.get("status", "queued"))
        stage = str(task.get("stage", "parse"))
        if kind not in TASK_KINDS or status not in TASK_STATUSES or stage not in TASK_STAGES:
            raise WorkbenchPersistenceError("INVALID_TASK_RECORD")
        percent = task.get("percent")
        if percent is not None and (isinstance(percent, bool) or not isinstance(percent, (int, float)) or not 0 <= percent <= 100):
            raise WorkbenchPersistenceError("INVALID_TASK_PROGRESS")
        now = utc_now()
        process_binding = _normalize_process_binding(task.get("process_binding"))
        _validate_counter_map(task.get("counters", {}))
        _validate_non_negative_int(task.get("input_revision", 0), "INVALID_TASK_RECORD")
        _validate_non_negative_int(task.get("attempt", 0), "INVALID_TASK_RECORD")
        _validate_error_fields(task.get("error_code"), task.get("error_summary"))
        values = (
            task_id, 1, case_id, kind, status, stage, percent,
            json_text(task.get("counters", {})), int(task.get("input_revision", 0)),
            int(task.get("attempt", 0)), None if process_binding is None else json_text(process_binding),
            task.get("error_code"), task.get("error_summary"), bool_int(bool(task.get("cancel_requested", False))),
            normalize_utc(task.get("created_at")), normalize_optional_utc(task.get("started_at")), normalize_optional_utc(task.get("finished_at")), 0,
        )
        with self.database.transaction() as connection:
            try:
                connection.execute(
                    "INSERT INTO task_records(task_id, schema_version, case_id, kind, status, stage, percent, counters_json, input_revision, attempt, process_binding_json, error_code, error_summary, cancel_requested, created_at, started_at, finished_at, revision) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    values,
                )
            except Exception as error:
                raise WorkbenchPersistenceError("TASK_CREATE_FAILED") from error
        return self.get(task_id)

    def get(self, task_id: str) -> dict[str, Any]:
        task_id = validate_opaque_id(task_id)
        connection = self.database.connect()
        try:
            row = connection.execute("SELECT * FROM task_records WHERE task_id = ?", (task_id,)).fetchone()
        finally:
            connection.close()
        if row is None:
            raise WorkbenchPersistenceError("TASK_NOT_FOUND")
        return _task_dict(row)

    def update(self, task_id: str, changes: Mapping[str, Any], expected_revision: int) -> dict[str, Any]:
        task_id = validate_opaque_id(task_id)
        allowed = {"status", "stage", "percent", "counters", "process_binding", "error_code", "error_summary", "cancel_requested", "started_at", "finished_at", "attempt"}
        if any(key not in allowed for key in changes):
            raise WorkbenchPersistenceError("INVALID_TASK_UPDATE")
        current = self.get(task_id)
        next_value = {**current, **changes}
        if next_value["status"] != current["status"] and next_value["status"] not in TASK_TRANSITIONS[current["status"]]:
            raise WorkbenchPersistenceError("INVALID_TASK_TRANSITION")
        _validate_task_values(next_value)
        next_value["started_at"] = normalize_optional_utc(next_value.get("started_at"))
        next_value["finished_at"] = normalize_optional_utc(next_value.get("finished_at"))
        with self.database.transaction() as connection:
            row = connection.execute("SELECT revision FROM task_records WHERE task_id = ?", (task_id,)).fetchone()
            if row is None:
                raise WorkbenchPersistenceError("TASK_NOT_FOUND")
            actual = int(row[0])
            if actual != expected_revision:
                raise RevisionConflictError("task", expected_revision, actual)
            updated = connection.execute(
                "UPDATE task_records SET status = ?, stage = ?, percent = ?, counters_json = ?, process_binding_json = ?, error_code = ?, error_summary = ?, cancel_requested = ?, attempt = ?, started_at = ?, finished_at = ?, revision = revision + 1 WHERE task_id = ? AND revision = ?",
                (next_value["status"], next_value["stage"], next_value["percent"], json_text(next_value["counters"]), None if next_value.get("process_binding") is None else json_text(next_value["process_binding"]), next_value.get("error_code"), next_value.get("error_summary"), bool_int(bool(next_value["cancel_requested"])), next_value["attempt"], next_value.get("started_at"), next_value.get("finished_at"), task_id, expected_revision),
            )
            if updated.rowcount != 1:
                raise RevisionConflictError("task", expected_revision, actual)
        return self.get(task_id)

    def mark_running_tasks_interrupted(self) -> list[dict[str, Any]]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT task_id, revision FROM task_records WHERE status IN ('running', 'cancelling')"
            ).fetchall()
            for row in rows:
                updated = connection.execute(
                    "UPDATE task_records SET status = 'interrupted', error_code = 'TASK_RESTART_INTERRUPTED', error_summary = 'TASK_RESTART_INTERRUPTED', revision = revision + 1 WHERE task_id = ? AND revision = ? AND status IN ('running', 'cancelling')",
                    (row[0], row[1]),
                )
                if updated.rowcount != 1:
                    raise RevisionConflictError("task", int(row[1]), int(row[1]))
        return [self.get(str(row[0])) for row in rows]


def _validate_task_values(task: Mapping[str, Any]) -> None:
    if task["status"] not in TASK_STATUSES or task["stage"] not in TASK_STAGES:
        raise WorkbenchPersistenceError("INVALID_TASK_RECORD")
    percent = task.get("percent")
    if percent is not None and (isinstance(percent, bool) or not isinstance(percent, (int, float)) or not 0 <= percent <= 100):
        raise WorkbenchPersistenceError("INVALID_TASK_PROGRESS")
    _validate_counter_map(task.get("counters"))
    _normalize_process_binding(task.get("process_binding"))
    _validate_non_negative_int(task.get("attempt", 0), "INVALID_TASK_RECORD")
    _validate_error_fields(task.get("error_code"), task.get("error_summary"))


def _validate_error_fields(error_code: Any, error_summary: Any) -> None:
    if error_code is not None:
        validate_safe_string(error_code, "INVALID_TASK_RECORD")
    if error_summary is not None:
        validate_safe_string(error_summary, "INVALID_TASK_RECORD")


def _validate_counter_map(value: Any) -> None:
    if not isinstance(value, Mapping) or any(
        not isinstance(key, str) or isinstance(number, bool) or not isinstance(number, (int, float))
        for key, number in value.items()
    ):
        raise WorkbenchPersistenceError("INVALID_TASK_PROGRESS")
    json_text(value)


def _normalize_process_binding(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise WorkbenchPersistenceError("INVALID_TASK_RECORD")
    if set(value) - {"process_tree_id", "staging_asset_id"}:
        raise WorkbenchPersistenceError("INVALID_TASK_RECORD")
    validate_opaque_id(value.get("process_tree_id"))
    if value.get("staging_asset_id") is not None:
        validate_opaque_id(value.get("staging_asset_id"))
    normalized = dict(value)
    json_text(normalized)
    return normalized


def _validate_non_negative_int(value: Any, code: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise WorkbenchPersistenceError(code)


def _task_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": int(row["schema_version"]), "task_id": row["task_id"], "case_id": row["case_id"],
        "kind": row["kind"], "status": row["status"], "stage": row["stage"], "percent": row["percent"],
        "counters": row_json(row, "counters_json"), "input_revision": int(row["input_revision"]),
        "attempt": int(row["attempt"]), "process_binding": None if row["process_binding_json"] is None else row_json(row, "process_binding_json"),
        "error_code": row["error_code"], "error_summary": row["error_summary"], "cancel_requested": bool(row["cancel_requested"]),
        "created_at": row["created_at"], "started_at": row["started_at"], "finished_at": row["finished_at"], "revision": int(row["revision"]),
    }
