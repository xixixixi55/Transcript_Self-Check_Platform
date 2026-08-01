"""The only repository entry allowed to create a queued archive attempt."""

from __future__ import annotations

import secrets
from typing import Any

from .archive_context_binding_repository import replace_active_binding
from .archive_publish_fence_repository import invalidate_pending, reject_if_active
from .archive_attempt_projection_repository import public_attempt
from .workbench_database import WorkbenchDatabase, utc_now
from .workbench_errors import RevisionConflictError, WorkbenchPersistenceError
from .workbench_serialization import validate_opaque_id


class ArchivePreparationRepository:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database

    def prepare(
        self, case_id: str, source_id: str, source_revision: int,
        context_id: str, expected_case_revision: int, draft_revision: int,
        report_hash: str, context_expires_at: str | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        case_id = validate_opaque_id(case_id)
        source_id = validate_opaque_id(source_id)
        if task_id is not None:
            task_id = validate_opaque_id(task_id)
        now = utc_now()
        attempt_id = f"attempt-{secrets.token_hex(20)}"
        with self.database.transaction() as connection:
            reject_if_active(connection, case_id=case_id)
            invalidate_pending(connection, case_id=case_id)
            shell = connection.execute(
                "SELECT source_id, lifecycle, report_available, revision FROM case_shells WHERE case_id = ?",
                (case_id,),
            ).fetchone()
            source = connection.execute(
                "SELECT case_id, revision, access_status FROM source_records WHERE source_id = ?", (source_id,),
            ).fetchone()
            draft = connection.execute(
                "SELECT revision FROM case_drafts WHERE case_id = ?", (case_id,),
            ).fetchone()
            if shell is None or source is None or source[0] != case_id or draft is None:
                raise WorkbenchPersistenceError("CASE_NOT_FOUND")
            if int(shell[3]) != expected_case_revision:
                raise RevisionConflictError("case_shell", expected_case_revision, int(shell[3]))
            if int(source[1]) != source_revision or source[2] != "available":
                raise WorkbenchPersistenceError("SOURCE_REVISION_CONFLICT")
            if int(draft[0]) != draft_revision or not report_hash:
                raise WorkbenchPersistenceError("DRAFT_REVISION_CONFLICT")
            if str(shell[1]) == "archive_queued":
                active = connection.execute(
                    "SELECT * FROM archive_attempts WHERE case_id = ? AND "
                    "deployment_instance_id = ? AND status IN ('accepted', 'running') "
                    "ORDER BY created_at DESC LIMIT 1",
                    (case_id, self.database.deployment_instance_id),
                ).fetchone()
                if active is None:
                    raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_NOT_ALLOWED")
                if (
                    active["source_id"] != source_id
                    or int(active["source_revision"] or active["input_revision"]) != source_revision
                    or int(active["draft_revision"] or 0) != draft_revision
                    or active["report_fingerprint"] != report_hash
                ):
                    raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_BINDING_MISMATCH")
                replace_active_binding(
                    connection, str(active["attempt_id"]), case_id, context_id,
                    source_id=source_id, source_revision=source_revision,
                    draft_revision=draft_revision, report_hash=report_hash,
                    expires_at=context_expires_at,
                )
                attempt_id = str(active["attempt_id"])
            elif not shell[2] or str(shell[1]) not in {"review_ready", "archive_deferred", "archive_interrupted"}:
                raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_NOT_ALLOWED")
            else:
                connection.execute(
                    "INSERT INTO archive_attempts(attempt_id, schema_version, case_id, "
                    "task_id, deployment_instance_id, source_id, input_revision, source_revision, "
                    "draft_revision, report_fingerprint, status, cleanup_status, error_code, "
                    "manifest_id, staging_root_id, staging_locator, ownership_marker_token, "
                    "process_pid, process_started_at, created_at, started_at, finished_at, revision) "
                    "VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, 'accepted', 'not_required', NULL, "
                    "NULL, NULL, NULL, NULL, NULL, NULL, ?, NULL, NULL, 0)",
                    (attempt_id, case_id, task_id, self.database.deployment_instance_id, source_id,
                     source_revision, source_revision, draft_revision, report_hash, now),
                )
                replace_active_binding(
                    connection, attempt_id, case_id, context_id,
                    source_id=source_id, source_revision=source_revision,
                    draft_revision=draft_revision, report_hash=report_hash,
                    expires_at=context_expires_at,
                )
                if connection.execute(
                    "UPDATE case_shells SET lifecycle = 'archive_queued', revision = revision + 1, updated_at = ? WHERE case_id = ? AND revision = ?",
                    (now, case_id, expected_case_revision),
                ).rowcount != 1:
                    raise RevisionConflictError("case_shell", expected_case_revision, expected_case_revision)
                if connection.execute(
                    "UPDATE case_drafts SET lifecycle = 'archive_queued', updated_at = ? WHERE case_id = ? AND revision = ?",
                    (now, case_id, draft_revision),
                ).rowcount != 1:
                    raise WorkbenchPersistenceError("DRAFT_REVISION_CONFLICT")
        return self._public(attempt_id)

    def reissue(
        self, case_id: str, source_id: str, source_revision: int,
        context_id: str, expected_case_revision: int, draft_revision: int,
        report_hash: str, context_expires_at: str | None = None,
    ) -> dict[str, Any]:
        case_id = validate_opaque_id(case_id)
        source_id = validate_opaque_id(source_id)
        with self.database.transaction() as connection:
            reject_if_active(connection, case_id=case_id)
            invalidate_pending(connection, case_id=case_id)
            shell = connection.execute(
                "SELECT revision, lifecycle FROM case_shells WHERE case_id = ?", (case_id,),
            ).fetchone()
            source = connection.execute(
                "SELECT revision, access_status FROM source_records WHERE source_id = ? AND case_id = ?",
                (source_id, case_id),
            ).fetchone()
            draft = connection.execute("SELECT revision FROM case_drafts WHERE case_id = ?", (case_id,)).fetchone()
            attempt = connection.execute(
                "SELECT attempt_id FROM archive_attempts WHERE case_id = ? AND "
                "deployment_instance_id = ? AND status = 'accepted' "
                "ORDER BY created_at DESC LIMIT 1",
                (case_id, self.database.deployment_instance_id),
            ).fetchone()
            if shell is None or source is None or attempt is None or draft is None:
                raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_NOT_ALLOWED")
            if int(shell[0]) != expected_case_revision or shell[1] != "archive_queued":
                raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_NOT_ALLOWED")
            if int(source[0]) != source_revision or source[1] != "available" or int(draft[0]) != draft_revision:
                raise WorkbenchPersistenceError("SOURCE_REVISION_CONFLICT")
            row = connection.execute(
                "SELECT * FROM archive_attempts WHERE attempt_id = ? AND status = 'accepted'", (attempt[0],),
            ).fetchone()
            if row is None or row["report_fingerprint"] != report_hash:
                raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_BINDING_MISMATCH")
            connection.execute(
                "UPDATE archive_attempts SET source_id = ?, input_revision = ?, source_revision = ?, draft_revision = ?, revision = revision + 1 WHERE attempt_id = ? AND status = 'accepted'",
                (source_id, source_revision, source_revision, draft_revision, attempt[0]),
            )
            replace_active_binding(
                connection, str(attempt[0]), case_id, context_id,
                source_id=source_id, source_revision=source_revision,
                draft_revision=draft_revision, report_hash=report_hash,
                expires_at=context_expires_at,
            )
        return self._public(str(attempt[0]))

    def _public(self, attempt_id: str) -> dict[str, Any]:
        connection = self.database.connect()
        try:
            row = connection.execute("SELECT * FROM archive_attempts WHERE attempt_id = ?", (attempt_id,)).fetchone()
        finally:
            connection.close()
        if row is None:
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_NOT_FOUND")
        return public_attempt(row)
