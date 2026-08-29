"""以原子方式删除工作台拥有的案件记录。"""

from __future__ import annotations

from typing import Any

from ..workbench_database import WorkbenchDatabase
from ..workbench_errors import WorkbenchPersistenceError
from ..workbench_serialization import validate_opaque_id


class CaseDeletionRepository:
    """删除明确确认案件的所有工作台记录。"""

    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database

    def preflight(self, case_id: str) -> dict[str, Any]:
        case_id = validate_opaque_id(case_id)
        with self.database.connect() as connection:
            shell = self._shell(connection, case_id)
            if shell is None:
                raise WorkbenchPersistenceError("CASE_NOT_FOUND")
            return {"allowed": True, "blockers": []}

    def delete_case(self, case_id: str) -> dict[str, Any]:
        case_id = validate_opaque_id(case_id)
        with self.database.transaction() as connection:
            shell = self._shell(connection, case_id)
            if shell is None:
                raise WorkbenchPersistenceError("CASE_NOT_FOUND")
            self._delete_related_records(connection, case_id)
            deleted = connection.execute(
                "DELETE FROM case_shells WHERE case_id=? AND deployment_instance_id=?",
                (case_id, self.database.deployment_instance_id),
            )
            if deleted.rowcount != 1:
                raise WorkbenchPersistenceError("CASE_DELETE_FAILED")
        return {"case_id": case_id, "deleted": True}

    def _shell(self, connection: Any, case_id: str) -> Any:
        return connection.execute(
            "SELECT lifecycle,record_cleaned FROM case_shells "
            "WHERE case_id=? AND deployment_instance_id=?",
            (case_id, self.database.deployment_instance_id),
        ).fetchone()

    def _delete_related_records(self, connection: Any, case_id: str) -> None:
        scoped = (
            "archive_input_snapshots", "archive_publish_fences", "archive_publish_intents",
            "archive_attempts", "formal_word_artifacts", "case_cleanup_runs", "case_retention_records",
        )
        connection.execute("DELETE FROM archive_context_bindings WHERE case_id=?", (case_id,))
        for table in scoped:
            connection.execute(
                f"DELETE FROM {table} WHERE case_id=? AND deployment_instance_id=?",
                (case_id, self.database.deployment_instance_id),
            )
        for table in (
            "archive_assets", "archive_plans", "source_records",
            "task_records", "case_drafts", "edit_leases", "asset_references", "audit_events",
        ):
            connection.execute(f"DELETE FROM {table} WHERE case_id=?", (case_id,))
