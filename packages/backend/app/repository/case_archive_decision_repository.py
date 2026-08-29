"""解析后归档时机决策的原子持久化。"""

from __future__ import annotations

from .workbench_constants import CASE_TRANSITIONS
from .workbench_database import WorkbenchDatabase, utc_now
from .workbench_errors import WorkbenchPersistenceError
from .archive.archive_publish_fence_repository import invalidate_pending, reject_if_active


class CaseArchiveDecisionRepository:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database

    def decide(self, case_id: str, decision: str, expected_revision: int) -> None:
        if decision == "immediate":
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_REQUIRED")
        target = {"deferred": "archive_deferred"}.get(decision)
        if target is None:
            raise WorkbenchPersistenceError("INVALID_ARCHIVE_DECISION")
        now = utc_now()
        with self.database.transaction() as connection:
            reject_if_active(connection, case_id=case_id)
            invalidate_pending(connection, case_id=case_id)
            shell = connection.execute(
                "SELECT lifecycle, report_available, revision FROM case_shells WHERE case_id = ?", (case_id,),
            ).fetchone()
            draft = connection.execute("SELECT 1 FROM case_drafts WHERE case_id = ?", (case_id,)).fetchone()
            if shell is None:
                raise WorkbenchPersistenceError("CASE_NOT_FOUND")
            if not shell[1] or draft is None:
                raise WorkbenchPersistenceError("DRAFT_NOT_REVIEWABLE")
            if int(shell[2]) != expected_revision:
                raise WorkbenchPersistenceError("REVISION_CONFLICT")
            current = str(shell[0])
            if current != target and target not in CASE_TRANSITIONS.get(current, set()):
                raise WorkbenchPersistenceError("INVALID_STATE_TRANSITION")
            if current != target:
                updated = connection.execute(
                    "UPDATE case_shells SET lifecycle = ?, revision = revision + 1, updated_at = ? WHERE case_id = ? AND revision = ?",
                    (target, now, case_id, expected_revision),
                )
                if updated.rowcount != 1:
                    raise WorkbenchPersistenceError("REVISION_CONFLICT")
                connection.execute(
                    "UPDATE case_drafts SET lifecycle = ?, updated_at = ? WHERE case_id = ?",
                    (target, now, case_id),
                )
