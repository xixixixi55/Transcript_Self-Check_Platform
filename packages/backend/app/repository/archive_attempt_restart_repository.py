"""Transactional runtime-state normalization for archive restart recovery."""

from __future__ import annotations

import json
from typing import Any

from .archive_attempt_projection_repository import internal_attempt
from .archive_context_binding_repository import deactivate_bindings
from .workbench_constants import ARCHIVE_TASK_ACTIONS
from .workbench_database import WorkbenchDatabase, utc_now
from .workbench_errors import WorkbenchPersistenceError
from .workbench_repository_helpers import json_text
from .workbench_serialization import validate_opaque_id


def normalize_runtime_after_restart(database: WorkbenchDatabase) -> list[dict[str, Any]]:
    """Clear stale runtime state before any durable evidence is inspected."""
    now = utc_now()
    with database.transaction() as connection:
        rows = connection.execute(
            "SELECT attempt_id, case_id, status FROM archive_attempts "
            "WHERE deployment_instance_id=? AND (status IN ('accepted', 'running') OR "
            "(status = 'failed' AND EXISTS (SELECT 1 FROM archive_publish_intents i "
            "WHERE i.attempt_id = archive_attempts.attempt_id "
            "AND i.deployment_instance_id=archive_attempts.deployment_instance_id "
            "AND i.phase NOT IN ('verified', 'conflict'))) "
            ") ORDER BY created_at, attempt_id",
            (database.deployment_instance_id,),
        ).fetchall()
        for row in rows:
            updated = connection.execute(
                "UPDATE archive_attempts SET status = 'interrupted', "
                "error_code = 'ARCHIVE_RESTART_PENDING_VERIFICATION', finished_at = ?, "
                "revision = revision + 1 WHERE attempt_id = ? AND deployment_instance_id=? "
                "AND status IN ('accepted', 'running', 'failed')",
                (now, row["attempt_id"], database.deployment_instance_id),
            )
            if updated.rowcount != 1:
                raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_STATE_INVALID")
            deactivate_bindings(connection, row["attempt_id"])
            shell_updated = connection.execute(
                "UPDATE case_shells SET lifecycle = 'archive_interrupted', revision = revision + 1, updated_at = ? "
                "WHERE case_id = ? AND lifecycle IN ('archive_queued', 'archiving')",
                (now, row["case_id"]),
            )
            if shell_updated.rowcount:
                draft_updated = connection.execute(
                    "UPDATE case_drafts SET lifecycle = 'archive_interrupted', updated_at = ? "
                    "WHERE case_id = ? AND lifecycle IN ('archive_queued', 'archiving')",
                    (now, row["case_id"]),
                )
                if draft_updated.rowcount != 1:
                    raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_CONFLICT")
    return [internal_attempt(_row(database, str(row["attempt_id"]))) for row in rows]


def interrupt_attempt(database: WorkbenchDatabase, attempt_id: str) -> dict[str, Any]:
    attempt_id = validate_opaque_id(attempt_id)
    now = utc_now()
    with database.transaction() as connection:
        row = connection.execute(
            "SELECT case_id, status FROM archive_attempts WHERE attempt_id = ? "
            "AND deployment_instance_id=? AND (status IN ('accepted', 'running') OR (status = 'failed' AND EXISTS ("
            "SELECT 1 FROM archive_publish_intents i WHERE i.attempt_id = archive_attempts.attempt_id "
            "AND i.deployment_instance_id=archive_attempts.deployment_instance_id "
            "AND i.phase NOT IN ('verified', 'conflict'))))",
            (attempt_id, database.deployment_instance_id),
        ).fetchone()
        if row is None:
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_STATE_INVALID")
        _interrupt_attempt_in_transaction(
            connection, attempt_id, row["case_id"], now,
            deployment_instance_id=database.deployment_instance_id,
            error_code="ARCHIVE_RESTART_INTERRUPTED", allow_failed=True,
        )
    return internal_attempt(_row(database, attempt_id))


def interrupt_owned_claim(
    database: WorkbenchDatabase, *, task_id: str, owner_token: str,
    attempt_id: str, task_revision: int,
) -> str:
    """Re-read and CAS-settle the current local claim after bounded stop.

    ``task_revision`` is retained for the caller contract and diagnostics only;
    shutdown must never use that stale snapshot as the authority.
    """
    task_id = validate_opaque_id(task_id)
    owner_token = validate_opaque_id(owner_token)
    attempt_id = validate_opaque_id(attempt_id)
    del task_revision
    for _ in range(3):
        now = utc_now()
        try:
            with database.transaction() as connection:
                task = connection.execute(
                    "SELECT * FROM task_records WHERE task_id=? AND kind='archive' "
                    "AND deployment_instance_id=?",
                    (task_id, database.deployment_instance_id),
                ).fetchone()
                if task is None:
                    return "ownership_lost"
                if task["status"] == "succeeded":
                    return "succeeded" if _publication_is_durable(
                        connection, attempt_id, database.deployment_instance_id,
                    ) else "unresolved"
                if task["status"] not in {"running", "cancelling"}:
                    return "not_interruptible"
                binding = _binding(task["process_binding_json"])
                if (
                    binding.get("process_tree_id") != owner_token
                    or binding.get("staging_asset_id") != attempt_id
                ):
                    return "ownership_lost"
                attempt = connection.execute(
                    "SELECT * FROM archive_attempts WHERE attempt_id=? AND task_id=? "
                    "AND deployment_instance_id=? AND case_id=?",
                    (attempt_id, task_id, database.deployment_instance_id, task["case_id"]),
                ).fetchone()
                if attempt is None:
                    _settle_task(connection, task, attempt_id, now, succeeded=False)
                    return "interrupted"
                fence = connection.execute(
                    "SELECT task_id, deployment_instance_id, status FROM archive_publish_fences "
                    "WHERE attempt_id=? AND deployment_instance_id=? "
                    "ORDER BY created_at DESC LIMIT 1",
                    (attempt_id, database.deployment_instance_id),
                ).fetchone()
                if fence is not None and (
                    fence["task_id"] != task_id
                    or fence["deployment_instance_id"] != database.deployment_instance_id
                    or fence["status"] not in {
                        "active", "pending_verification", "consumed",
                    }
                ):
                    return "ownership_lost"
                if attempt["status"] == "succeeded" and _publication_is_durable(
                    connection, attempt_id, database.deployment_instance_id,
                ):
                    _settle_task(connection, task, attempt_id, now, succeeded=True)
                    return "succeeded"
                if attempt["status"] in {"accepted", "running"}:
                    _interrupt_attempt_in_transaction(
                        connection, attempt_id, task["case_id"], now,
                        deployment_instance_id=database.deployment_instance_id,
                    )
                elif attempt["status"] not in {"failed", "interrupted", "succeeded"}:
                    return "not_interruptible"
                _settle_task(connection, task, attempt_id, now, succeeded=False)
                return "interrupted"
        except WorkbenchPersistenceError as error:
            if error.code in {"ARCHIVE_TASK_STATE_INVALID", "ARCHIVE_ATTEMPT_STATE_INVALID"}:
                continue
            raise
    return "unresolved"


def _publication_is_durable(
    connection: Any, attempt_id: str, deployment_instance_id: str,
) -> bool:
    row = connection.execute(
        "SELECT phase, publication_status, publication_digest, publication_file_set_json "
        "FROM archive_publish_intents WHERE attempt_id=? AND deployment_instance_id=?",
        (attempt_id, deployment_instance_id),
    ).fetchone()
    return bool(
        row is not None and row["phase"] == "verified"
        and row["publication_status"] == "verified"
        and row["publication_digest"] and row["publication_file_set_json"]
    )


def _interrupt_attempt_in_transaction(
    connection: Any, attempt_id: str, case_id: str, now: str, *,
    deployment_instance_id: str,
    error_code: str = "ARCHIVE_RUNTIME_INTERRUPTED", allow_failed: bool = False,
) -> None:
    statuses = "('accepted', 'running', 'failed')" if allow_failed else "('accepted', 'running')"
    updated = connection.execute(
        f"UPDATE archive_attempts SET status = 'interrupted', error_code = ?, "
        f"finished_at = ?, revision = revision + 1 WHERE attempt_id = ? "
        f"AND deployment_instance_id=? AND status IN {statuses}",
        (error_code, now, attempt_id, deployment_instance_id),
    )
    if updated.rowcount != 1:
        raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_STATE_INVALID")
    deactivate_bindings(connection, attempt_id)
    connection.execute(
        "UPDATE archive_publish_fences SET status = 'pending_verification', "
        "reason = 'ARCHIVE_RUNTIME_INTERRUPTED', updated_at = ? "
        "WHERE attempt_id = ? AND deployment_instance_id=? AND status = 'active'",
        (now, attempt_id, deployment_instance_id),
    )
    connection.execute(
        "UPDATE case_shells SET lifecycle = 'archive_interrupted', revision = revision + 1, updated_at = ? "
        "WHERE case_id = ? AND lifecycle IN ('archive_queued', 'archiving')",
        (now, case_id),
    )
    connection.execute(
        "UPDATE case_drafts SET lifecycle = 'archive_interrupted', updated_at = ? "
        "WHERE case_id = ? AND lifecycle IN ('archive_queued', 'archiving')",
        (now, case_id),
    )


def _settle_task(connection: Any, task: Any, attempt_id: str, now: str, *, succeeded: bool) -> None:
    if succeeded:
        values = (
            "succeeded", "completed", 100, task["process_binding_json"], None, None, 0,
            now, now, "released", json_text(ARCHIVE_TASK_ACTIONS["succeeded"]),
        )
    else:
        values = (
            "interrupted", task["stage"], task["percent"],
            json_text({"staging_asset_id": attempt_id}), "ARCHIVE_RUNTIME_INTERRUPTED",
            "Archive runtime stopped before completion.", int(task["cancel_requested"]),
            now, now, "waiting_reclaim", json_text(ARCHIVE_TASK_ACTIONS["interrupted"]),
        )
    updated = connection.execute(
        "UPDATE task_records SET status=?, stage=?, percent=?, process_binding_json=?, "
        "error_code=?, error_summary=?, cancel_requested=?, updated_at=?, finished_at=?, "
        "worker_state=?, allowed_actions_json=?, revision=revision+1 "
        "WHERE task_id=? AND deployment_instance_id=? AND revision=? "
        "AND status IN ('running', 'cancelling')",
        (*values, task["task_id"], task["deployment_instance_id"], int(task["revision"])),
    )
    if updated.rowcount != 1:
        raise WorkbenchPersistenceError("ARCHIVE_TASK_STATE_INVALID")


def _binding(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _row(database: WorkbenchDatabase, attempt_id: str) -> Any:
    connection = database.connect()
    try:
        return connection.execute(
            "SELECT * FROM archive_attempts WHERE attempt_id = ? AND deployment_instance_id=?",
            (attempt_id, database.deployment_instance_id),
        ).fetchone()
    finally:
        connection.close()
