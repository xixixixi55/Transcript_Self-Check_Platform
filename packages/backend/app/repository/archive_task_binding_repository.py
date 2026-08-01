"""Atomic task/attempt binding; the public API never supplies these IDs."""

from __future__ import annotations

from .workbench_database import WorkbenchDatabase, utc_now
from .workbench_errors import WorkbenchPersistenceError
from .workbench_repository_helpers import json_text, row_json
from .workbench_serialization import validate_opaque_id


def bind_archive_task_attempt(
    database: WorkbenchDatabase, task_id: str, attempt_id: str,
) -> None:
    task_id = validate_opaque_id(task_id)
    attempt_id = validate_opaque_id(attempt_id)
    now = utc_now()
    with database.transaction() as connection:
        task = connection.execute(
            "SELECT case_id, status, deployment_instance_id, process_binding_json "
            "FROM task_records WHERE task_id=? AND kind='archive'", (task_id,),
        ).fetchone()
        attempt = connection.execute(
            "SELECT task_id, case_id, deployment_instance_id, status "
            "FROM archive_attempts WHERE attempt_id=? AND deployment_instance_id=?",
            (attempt_id, database.deployment_instance_id),
        ).fetchone()
        if task is None or attempt is None:
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_BINDING_MISMATCH")
        if task["deployment_instance_id"] != database.deployment_instance_id:
            raise WorkbenchPersistenceError("ARCHIVE_DEPLOYMENT_MISMATCH")
        if task["status"] != "queued" or task["case_id"] != attempt["case_id"]:
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_BINDING_MISMATCH")
        if attempt["deployment_instance_id"] not in (None, database.deployment_instance_id):
            raise WorkbenchPersistenceError("ARCHIVE_DEPLOYMENT_MISMATCH")
        if attempt["status"] not in {"accepted", "running"}:
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_BINDING_MISMATCH")
        if attempt["task_id"] not in (None, task_id):
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_ALREADY_BOUND")
        if task["process_binding_json"] is not None:
            current_binding = row_json(task, "process_binding_json")
            if current_binding.get("staging_asset_id") == attempt_id:
                return
            raise WorkbenchPersistenceError("ARCHIVE_TASK_ALREADY_BOUND")
        if attempt["task_id"] is None and connection.execute(
            "UPDATE archive_attempts SET task_id=?, deployment_instance_id=?, "
            "revision=revision+1 WHERE attempt_id=? AND task_id IS NULL "
            "AND (deployment_instance_id IS NULL OR deployment_instance_id=?)",
            (task_id, database.deployment_instance_id, attempt_id,
             database.deployment_instance_id),
        ).rowcount != 1:
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_ALREADY_BOUND")
        if connection.execute(
            "UPDATE task_records SET process_binding_json=?, updated_at=?, "
            "revision=revision+1 WHERE task_id=? AND kind='archive' "
            "AND deployment_instance_id=? AND status='queued' "
            "AND process_binding_json IS NULL",
            (json_text({"staging_asset_id": attempt_id}), now, task_id,
             database.deployment_instance_id),
        ).rowcount != 1:
            raise WorkbenchPersistenceError("ARCHIVE_TASK_ALREADY_BOUND")
