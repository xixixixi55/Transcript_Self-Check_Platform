"""Transactional runtime-state normalization for archive restart recovery."""

from __future__ import annotations

from typing import Any

from .archive_attempt_projection_repository import internal_attempt
from .archive_context_binding_repository import deactivate_bindings
from .workbench_database import WorkbenchDatabase, utc_now
from .workbench_errors import WorkbenchPersistenceError
from .workbench_serialization import validate_opaque_id


def normalize_runtime_after_restart(database: WorkbenchDatabase) -> list[dict[str, Any]]:
    """Clear stale runtime state before any durable evidence is inspected."""
    now = utc_now()
    with database.transaction() as connection:
        rows = connection.execute(
            "SELECT attempt_id, case_id, status FROM archive_attempts "
            "WHERE status IN ('accepted', 'running') OR "
            "(status = 'failed' AND EXISTS (SELECT 1 FROM archive_publish_intents i "
            "WHERE i.attempt_id = archive_attempts.attempt_id AND i.phase NOT IN ('verified', 'conflict'))) "
            "ORDER BY created_at, attempt_id",
        ).fetchall()
        for row in rows:
            updated = connection.execute(
                "UPDATE archive_attempts SET status = 'interrupted', "
                "error_code = 'ARCHIVE_RESTART_PENDING_VERIFICATION', finished_at = ?, "
                "revision = revision + 1 WHERE attempt_id = ? AND status IN ('accepted', 'running', 'failed')",
                (now, row["attempt_id"]),
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
            "SELECT case_id FROM archive_attempts WHERE attempt_id = ? "
            "AND (status IN ('accepted', 'running') OR (status = 'failed' AND EXISTS ("
            "SELECT 1 FROM archive_publish_intents i WHERE i.attempt_id = archive_attempts.attempt_id "
            "AND i.phase NOT IN ('verified', 'conflict'))))",
            (attempt_id,),
        ).fetchone()
        if row is None:
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_STATE_INVALID")
        updated = connection.execute(
            "UPDATE archive_attempts SET status = 'interrupted', error_code = 'ARCHIVE_RESTART_INTERRUPTED', "
            "finished_at = ?, revision = revision + 1 WHERE attempt_id = ?",
            (now, attempt_id),
        )
        if updated.rowcount != 1:
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_STATE_INVALID")
        deactivate_bindings(connection, attempt_id)
        connection.execute(
            "UPDATE archive_publish_fences SET status = 'pending_verification', "
            "reason = 'ARCHIVE_RUNTIME_INTERRUPTED', updated_at = ? "
            "WHERE attempt_id = ? AND status = 'active'",
            (now, attempt_id),
        )
        connection.execute(
            "UPDATE case_shells SET lifecycle = 'archive_interrupted', revision = revision + 1, updated_at = ? "
            "WHERE case_id = ? AND lifecycle IN ('archive_queued', 'archiving')",
            (now, row["case_id"]),
        )
        connection.execute(
            "UPDATE case_drafts SET lifecycle = 'archive_interrupted', updated_at = ? "
            "WHERE case_id = ? AND lifecycle IN ('archive_queued', 'archiving')",
            (now, row["case_id"]),
        )
    return internal_attempt(_row(database, attempt_id))


def _row(database: WorkbenchDatabase, attempt_id: str) -> Any:
    connection = database.connect()
    try:
        return connection.execute(
            "SELECT * FROM archive_attempts WHERE attempt_id = ?", (attempt_id,),
        ).fetchone()
    finally:
        connection.close()
