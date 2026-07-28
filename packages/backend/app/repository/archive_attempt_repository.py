"""Persistent, path-free public views and private recovery data for archive attempts."""

from __future__ import annotations

import secrets
from typing import Any

from .workbench_constants import ARCHIVE_ATTEMPT_STATUSES, ARCHIVE_CLEANUP_STATUSES
from .workbench_database import WorkbenchDatabase, utc_now
from .workbench_errors import RevisionConflictError, WorkbenchPersistenceError
from .archive_attempt_projection_repository import internal_attempt, public_attempt
from .workbench_serialization import validate_opaque_id, validate_safe_string


class ArchiveAttemptRepository:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database

    def accept(
        self, case_id: str, source_id: str, source_revision: int,
        expected_case_revision: int,
    ) -> dict[str, Any]:
        case_id = validate_opaque_id(case_id)
        source_id = validate_opaque_id(source_id)
        now = utc_now()
        attempt_id = f"attempt-{secrets.token_hex(20)}"
        with self.database.transaction() as connection:
            shell = connection.execute(
                "SELECT source_id, lifecycle, report_available, revision FROM case_shells WHERE case_id = ?",
                (case_id,),
            ).fetchone()
            source = connection.execute(
                "SELECT case_id, revision FROM source_records WHERE source_id = ?", (source_id,),
            ).fetchone()
            if shell is None or source is None or source[0] != case_id:
                raise WorkbenchPersistenceError("CASE_NOT_FOUND")
            if int(shell[3]) != expected_case_revision:
                raise RevisionConflictError("case_shell", expected_case_revision, int(shell[3]))
            if int(source[1]) != source_revision:
                raise WorkbenchPersistenceError("SOURCE_REVISION_CONFLICT")
            if not shell[2] or str(shell[1]) not in {"review_ready", "archive_deferred", "archive_interrupted"}:
                raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_NOT_ALLOWED")
            connection.execute(
                "INSERT INTO archive_attempts(attempt_id, schema_version, case_id, source_id, input_revision, status, cleanup_status, error_code, manifest_id, staging_root_id, staging_locator, ownership_marker_token, process_pid, process_started_at, created_at, started_at, finished_at, revision) VALUES (?, 1, ?, ?, ?, 'accepted', 'not_required', NULL, NULL, NULL, NULL, NULL, NULL, NULL, ?, NULL, NULL, 0)",
                (attempt_id, case_id, source_id, source_revision, now),
            )
            updated = connection.execute(
                "UPDATE case_shells SET lifecycle = 'archive_queued', revision = revision + 1, updated_at = ? WHERE case_id = ? AND revision = ?",
                (now, case_id, expected_case_revision),
            )
            if updated.rowcount != 1:
                raise RevisionConflictError("case_shell", expected_case_revision, expected_case_revision)
            connection.execute(
                "UPDATE case_drafts SET lifecycle = 'archive_queued', updated_at = ? WHERE case_id = ?",
                (now, case_id),
            )
        return self.get_public(attempt_id)

    def get_public(self, attempt_id: str) -> dict[str, Any]:
        row = self._get_row(attempt_id)
        return public_attempt(row)

    def reissue_context(
        self, case_id: str, source_id: str, source_revision: int,
        expected_case_revision: int,
    ) -> dict[str, Any]:
        case_id = validate_opaque_id(case_id)
        source_id = validate_opaque_id(source_id)
        with self.database.transaction() as connection:
            shell = connection.execute(
                "SELECT revision, lifecycle FROM case_shells WHERE case_id = ?", (case_id,),
            ).fetchone()
            source = connection.execute(
                "SELECT revision FROM source_records WHERE source_id = ? AND case_id = ?",
                (source_id, case_id),
            ).fetchone()
            attempt = connection.execute(
                "SELECT attempt_id FROM archive_attempts WHERE case_id = ? AND status = 'accepted' ORDER BY created_at DESC LIMIT 1",
                (case_id,),
            ).fetchone()
            if shell is None or source is None or attempt is None:
                raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_NOT_ALLOWED")
            if int(shell[0]) != expected_case_revision or shell[1] != "archive_queued":
                raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_NOT_ALLOWED")
            if int(source[0]) != source_revision:
                raise WorkbenchPersistenceError("SOURCE_REVISION_CONFLICT")
            connection.execute(
                "UPDATE archive_attempts SET source_id = ?, input_revision = ?, revision = revision + 1 WHERE attempt_id = ? AND status = 'accepted'",
                (source_id, source_revision, attempt[0]),
            )
        return self.get_public(str(attempt[0]))

    def get_internal(self, attempt_id: str) -> dict[str, Any]:
        row = self._get_row(attempt_id)
        return internal_attempt(row)

    def list_public(self, case_id: str) -> list[dict[str, Any]]:
        case_id = validate_opaque_id(case_id)
        connection = self.database.connect()
        try:
            rows = connection.execute(
                "SELECT * FROM archive_attempts WHERE case_id = ? ORDER BY created_at DESC, attempt_id DESC",
                (case_id,),
            ).fetchall()
        finally:
            connection.close()
        return [public_attempt(row) for row in rows]

    def mark_running(self, attempt_id: str) -> dict[str, Any]:
        return self._transition(attempt_id, {"accepted"}, "running", started=True)

    def mark_succeeded(self, attempt_id: str, manifest_id: str) -> dict[str, Any]:
        validate_opaque_id(manifest_id)
        record = self.get_internal(attempt_id)
        cleanup = "succeeded" if record["staging_locator"] else "not_required"
        return self._transition(
            attempt_id, {"accepted", "running"}, "succeeded",
            manifest_id=manifest_id, cleanup_status=cleanup,
        )

    def mark_failed(self, attempt_id: str, error_code: str) -> dict[str, Any]:
        validate_safe_string(error_code, "INVALID_ARCHIVE_ATTEMPT")
        record = self.get_internal(attempt_id)
        cleanup = "pending" if record["staging_locator"] else "not_required"
        return self._transition(
            attempt_id, {"accepted", "running"}, "failed",
            error_code=error_code, cleanup_status=cleanup,
        )

    def bind_staging(self, attempt_id: str, locator: str, root_id: str, marker_token: str) -> None:
        with self.database.transaction() as connection:
            updated = connection.execute(
                "UPDATE archive_attempts SET staging_root_id = ?, staging_locator = ?, ownership_marker_token = ?, cleanup_status = 'pending', revision = revision + 1 WHERE attempt_id = ? AND status IN ('accepted', 'running')",
                (root_id, locator, marker_token, validate_opaque_id(attempt_id)),
            )
            if updated.rowcount != 1:
                raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_STATE_INVALID")

    def bind_process(self, attempt_id: str, pid: int, started_at: str) -> None:
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            raise WorkbenchPersistenceError("INVALID_ARCHIVE_ATTEMPT")
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE archive_attempts SET process_pid = ?, process_started_at = ?, revision = revision + 1 WHERE attempt_id = ? AND status = 'running'",
                (pid, started_at, validate_opaque_id(attempt_id)),
            )

    def mark_cleanup(self, attempt_id: str, status: str, error_code: str | None = None) -> dict[str, Any]:
        if status not in ARCHIVE_CLEANUP_STATUSES:
            raise WorkbenchPersistenceError("INVALID_ARCHIVE_ATTEMPT")
        with self.database.transaction() as connection:
            updated = connection.execute(
                "UPDATE archive_attempts SET cleanup_status = ?, error_code = COALESCE(?, error_code), revision = revision + 1 WHERE attempt_id = ? AND status IN ('failed', 'interrupted')",
                (status, error_code, validate_opaque_id(attempt_id)),
            )
            if updated.rowcount != 1:
                current = connection.execute("SELECT status FROM archive_attempts WHERE attempt_id = ?", (attempt_id,)).fetchone()
                if current is None:
                    raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_NOT_FOUND")
        return self.get_public(attempt_id)

    def recover_unfinished(self) -> list[dict[str, Any]]:
        now = utc_now()
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT attempt_id, case_id FROM archive_attempts WHERE status IN ('accepted', 'running')",
            ).fetchall()
            for row in rows:
                connection.execute(
                    "UPDATE archive_attempts SET status = 'interrupted', error_code = 'ARCHIVE_RESTART_INTERRUPTED', finished_at = ?, revision = revision + 1 WHERE attempt_id = ? AND status IN ('accepted', 'running')",
                    (now, row[0]),
                )
                updated = connection.execute(
                    "UPDATE case_shells SET lifecycle = 'archive_interrupted', revision = revision + 1, updated_at = ? WHERE case_id = ? AND lifecycle IN ('archive_queued', 'archiving')",
                    (now, row[1]),
                )
                if updated.rowcount:
                    connection.execute(
                        "UPDATE case_drafts SET lifecycle = 'archive_interrupted', updated_at = ? WHERE case_id = ?",
                        (now, row[1]),
                    )
        return [self.get_internal(str(row[0])) for row in rows]

    def interrupt_case(self, attempt_id: str) -> None:
        record = self.get_internal(attempt_id)
        now = utc_now()
        with self.database.transaction() as connection:
            updated = connection.execute(
                "UPDATE case_shells SET lifecycle = 'archive_interrupted', revision = revision + 1, updated_at = ? WHERE case_id = ? AND lifecycle IN ('archive_queued', 'archiving')",
                (now, record["case_id"]),
            )
            if updated.rowcount:
                connection.execute(
                    "UPDATE case_drafts SET lifecycle = 'archive_interrupted', updated_at = ? WHERE case_id = ?",
                    (now, record["case_id"]),
                )

    def _transition(self, attempt_id: str, allowed: set[str], target: str, **changes: Any) -> dict[str, Any]:
        attempt_id = validate_opaque_id(attempt_id)
        now = utc_now()
        assignments = ["status = ?", "revision = revision + 1"]
        values: list[Any] = [target]
        if changes.get("started"):
            assignments.append("started_at = ?")
            values.append(now)
        if "manifest_id" in changes:
            assignments.append("manifest_id = ?")
            values.append(changes["manifest_id"])
        if "error_code" in changes:
            assignments.extend(["error_code = ?", "finished_at = ?"])
            values.extend([changes["error_code"], now])
        elif target == "succeeded":
            assignments.append("finished_at = ?")
            values.append(now)
        if "cleanup_status" in changes:
            assignments.append("cleanup_status = ?")
            values.append(changes["cleanup_status"])
        values.append(attempt_id)
        placeholders = ", ".join("?" for _ in allowed)
        with self.database.transaction() as connection:
            row = connection.execute("SELECT status FROM archive_attempts WHERE attempt_id = ?", (attempt_id,)).fetchone()
            if row is None:
                raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_NOT_FOUND")
            if row[0] not in allowed:
                if row[0] == target:
                    return self.get_public(attempt_id)
                raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_STATE_INVALID")
            query = f"UPDATE archive_attempts SET {', '.join(assignments)} WHERE attempt_id = ? AND status IN ({placeholders})"
            cursor_values = [*values[:-1], values[-1], *allowed]
            if connection.execute(query, cursor_values).rowcount != 1:
                raise RevisionConflictError("archive_attempt", 0, 0)
        return self.get_public(attempt_id)

    def _get_row(self, attempt_id: str) -> Any:
        connection = self.database.connect()
        try:
            row = connection.execute("SELECT * FROM archive_attempts WHERE attempt_id = ?", (validate_opaque_id(attempt_id),)).fetchone()
        finally:
            connection.close()
        if row is None:
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_NOT_FOUND")
        if row["status"] not in ARCHIVE_ATTEMPT_STATUSES:
            raise WorkbenchPersistenceError("INVALID_ARCHIVE_ATTEMPT")
        return row
