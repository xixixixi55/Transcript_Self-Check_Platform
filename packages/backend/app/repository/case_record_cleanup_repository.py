"""Whitelist-only work-record cleanup inside the records transaction."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .workbench_database import WorkbenchDatabase
from .workbench_errors import WorkbenchPersistenceError
from .retention_repository_helpers import identifier

_RECOVERY_ATTEMPT_STATUSES = ("accepted", "running", "interrupted")

class CaseRecordCleanupRepository:
    """Apply the design matrix while the caller owns the SQLite transaction."""

    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database

    def compact_work_records(
        self, connection: Any, case_id: str, *, file_step_result: Any, now: str,
    ) -> None:
        case_id = identifier(case_id)
        snapshots = self._snapshots(connection, case_id)
        temporary_assets = self._temporary_assets(connection, case_id)
        self._assert_recovery(connection, case_id)
        self._validate_file_receipt(connection, file_step_result, snapshots, temporary_assets)
        formal_attempts, formal_tasks = self._formal_ids(connection, case_id)
        self._delete_snapshot_rows(connection, case_id)
        self._compact_formal_attempts(connection, formal_attempts)
        self._compact_formal_tasks(connection, formal_tasks)
        self._clear_source_task_bindings(connection, case_id)
        self._delete_inactive_contexts(connection, case_id)
        self._delete_orphan_attempts(connection, case_id, formal_attempts)
        self._delete_orphan_tasks(connection, case_id, formal_tasks)
        self._delete_temporary_assets(connection, case_id)
        self._delete_plans(connection, case_id)
        connection.execute(
            "DELETE FROM case_drafts WHERE case_id=? AND EXISTS ("
            "SELECT 1 FROM case_shells WHERE case_id=case_drafts.case_id AND deployment_instance_id=?)",
            (case_id, self.database.deployment_instance_id),
        )
        connection.execute("DELETE FROM asset_references WHERE case_id=?", (case_id,))
        self._compact_sources(connection, case_id, formal_attempts, now)
        if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise WorkbenchPersistenceError("CLEANUP_PRECONDITION_FAILED")
    def _snapshots(self, connection: Any, case_id: str) -> list[Mapping[str, Any]]:
        return connection.execute(
            "SELECT s.* FROM archive_input_snapshots s WHERE s.case_id=? AND s.deployment_instance_id=? "
            "ORDER BY s.snapshot_id",
            (case_id, self.database.deployment_instance_id),
        ).fetchall()
    def _temporary_assets(self, connection: Any, case_id: str) -> list[Mapping[str, Any]]:
        return connection.execute(
            "SELECT a.* FROM archive_assets a JOIN case_shells s ON s.case_id=a.case_id "
            "WHERE a.case_id=? AND s.deployment_instance_id=? AND a.asset_kind='staging' AND a.status='temporary'",
            (case_id, self.database.deployment_instance_id),
        ).fetchall()
    def _assert_recovery(self, connection: Any, case_id: str) -> None:
        placeholders = ",".join("?" for _ in _RECOVERY_ATTEMPT_STATUSES)
        if connection.execute(
            f"SELECT 1 FROM archive_attempts WHERE case_id=? AND deployment_instance_id=? AND "
            f"(status IN ({placeholders}) OR cleanup_status IN ('pending','unknown')) LIMIT 1",
            (case_id, self.database.deployment_instance_id, *_RECOVERY_ATTEMPT_STATUSES),
        ).fetchone() is not None:
            raise WorkbenchPersistenceError("RETENTION_SNAPSHOT_RECOVERY_REFERENCED")
        if connection.execute(
            "SELECT 1 FROM archive_context_bindings b JOIN case_shells s ON s.case_id=b.case_id "
            "WHERE b.case_id=? AND b.active=1 AND s.deployment_instance_id=? LIMIT 1",
            (case_id, self.database.deployment_instance_id),
        ).fetchone() is not None:
            raise WorkbenchPersistenceError("RETENTION_SNAPSHOT_RECOVERY_REFERENCED")

    def _validate_file_receipt(
        self, connection: Any, raw: Any, snapshots: list[Mapping[str, Any]], assets: list[Mapping[str, Any]],
    ) -> None:
        if not snapshots and not assets:
            return
        if not isinstance(raw, Mapping):
            try:
                raw = json.loads(raw) if isinstance(raw, str) else None
            except (TypeError, ValueError):
                raw = None
        if not isinstance(raw, Mapping) or raw.get("version") != 1 or raw.get("ownership_verified") is not True:
            raise WorkbenchPersistenceError("RETENTION_SNAPSHOT_OWNERSHIP_UNKNOWN")
        snapshot_ids = _id_set(raw.get("deleted_snapshot_ids"))
        asset_ids = _id_set(raw.get("deleted_asset_ids"))
        expected_snapshots = {str(row["snapshot_id"]) for row in snapshots}
        expected_assets = {str(row["asset_id"]) for row in assets}
        if snapshot_ids != expected_snapshots or asset_ids != expected_assets:
            raise WorkbenchPersistenceError("CLEANUP_SNAPSHOT_DELETE_FAILED")
        if any(row["status"] != "cleaned" for row in snapshots):
            raise WorkbenchPersistenceError("RETENTION_SNAPSHOT_ACTIVE")
        for row in assets:
            if row["task_id"] is None and row["plan_id"] is None:
                raise WorkbenchPersistenceError("RETENTION_OWNERSHIP_UNKNOWN")
            if not self._asset_ownership_is_current(connection, row):
                raise WorkbenchPersistenceError("RETENTION_OWNERSHIP_UNKNOWN")

    def _asset_ownership_is_current(self, connection: Any, row: Mapping[str, Any]) -> bool:
        task_owned = row["task_id"] is not None and connection.execute("SELECT 1 FROM task_records WHERE task_id=? AND case_id=? AND deployment_instance_id=?", (row["task_id"], row["case_id"], self.database.deployment_instance_id)).fetchone() is not None
        plan_owned = row["plan_id"] is not None and connection.execute("SELECT 1 FROM archive_plans WHERE plan_id=? AND case_id=?", (row["plan_id"], row["case_id"])).fetchone() is not None
        return task_owned or plan_owned

    def _formal_ids(self, connection: Any, case_id: str) -> tuple[set[str], set[str]]:
        attempts = connection.execute(
            "SELECT attempt_id,task_id,manifest_id FROM archive_attempts WHERE case_id=? AND deployment_instance_id=?",
            (case_id, self.database.deployment_instance_id),
        ).fetchall()
        referenced = {
            str(row[0]) for row in connection.execute(
                "SELECT attempt_id FROM archive_publish_intents WHERE case_id=? AND deployment_instance_id=? "
                "UNION SELECT attempt_id FROM archive_publish_fences WHERE case_id=? AND deployment_instance_id=?",
                (case_id, self.database.deployment_instance_id, case_id, self.database.deployment_instance_id),
            ).fetchall()
        }
        formal_attempts = {
            str(row["attempt_id"]) for row in attempts
            if row["manifest_id"] is not None or str(row["attempt_id"]) in referenced
        }
        formal_tasks = {
            str(row["task_id"]) for row in attempts
            if str(row["attempt_id"]) in formal_attempts and row["task_id"] is not None
        }
        for row in connection.execute(
            "SELECT task_id FROM archive_publish_intents WHERE case_id=? AND deployment_instance_id=? "
            "UNION SELECT task_id FROM archive_publish_fences WHERE case_id=? AND deployment_instance_id=?",
            (case_id, self.database.deployment_instance_id, case_id, self.database.deployment_instance_id),
        ).fetchall():
            if row[0] is not None:
                formal_tasks.add(str(row[0]))
        for row in connection.execute(
            "SELECT task_id FROM task_records WHERE case_id=? AND deployment_instance_id=? "
            "AND (publication_id IS NOT NULL OR word_artifact_id IS NOT NULL)",
            (case_id, self.database.deployment_instance_id),
        ).fetchall():
            if row[0] is not None:
                formal_tasks.add(str(row[0]))
        return formal_attempts, formal_tasks

    def _delete_snapshot_rows(self, connection: Any, case_id: str) -> None:
        connection.execute(
            "UPDATE archive_attempts SET input_snapshot_id=NULL,input_snapshot_root_id=NULL,"
            "input_snapshot_locator=NULL,input_snapshot_fingerprint=NULL,input_snapshot_status=NULL,revision=revision+1 "
            "WHERE case_id=? AND deployment_instance_id=?",
            (case_id, self.database.deployment_instance_id),
        )
        connection.execute(
            "DELETE FROM archive_input_snapshots WHERE case_id=? AND deployment_instance_id=?",
            (case_id, self.database.deployment_instance_id),
        )

    def _compact_formal_attempts(self, connection: Any, attempt_ids: set[str]) -> None:
        for attempt_id in attempt_ids:
            connection.execute(
                "UPDATE archive_attempts SET staging_root_id=NULL,staging_locator=NULL,ownership_marker_token=NULL,"
                "process_pid=NULL,process_started_at=NULL,revision=revision+1 WHERE attempt_id=? AND deployment_instance_id=?",
                (attempt_id, self.database.deployment_instance_id),
            )

    def _compact_formal_tasks(self, connection: Any, task_ids: set[str]) -> None:
        for task_id in task_ids:
            connection.execute("UPDATE task_records SET counters_json='{}',process_binding_json=NULL,error_summary=NULL,allowed_actions_json='[]',stage_label=NULL,stage_index=NULL,stage_count=NULL,last_heartbeat_at=NULL,output_bytes=NULL,output_volume_count=NULL,last_output_change_at=NULL,revision=revision+1 WHERE task_id=? AND deployment_instance_id=?", (task_id, self.database.deployment_instance_id))

    def _clear_source_task_bindings(self, connection: Any, case_id: str) -> None:
        connection.execute(
            "UPDATE source_records SET task_id=NULL WHERE case_id=? AND deployment_instance_id=?",
            (case_id, self.database.deployment_instance_id),
        )

    def _delete_inactive_contexts(self, connection: Any, case_id: str) -> None:
        connection.execute("DELETE FROM archive_context_bindings WHERE case_id=? AND active=0", (case_id,))

    def _delete_orphan_attempts(self, connection: Any, case_id: str, formal_ids: set[str]) -> None:
        rows = connection.execute(
            "SELECT attempt_id FROM archive_attempts WHERE case_id=? AND deployment_instance_id=?",
            (case_id, self.database.deployment_instance_id),
        ).fetchall()
        for row in rows:
            if str(row[0]) not in formal_ids:
                connection.execute("DELETE FROM archive_attempts WHERE attempt_id=?", (row[0],))

    def _delete_orphan_tasks(self, connection: Any, case_id: str, formal_ids: set[str]) -> None:
        rows = connection.execute(
            "SELECT task_id FROM task_records WHERE case_id=? AND deployment_instance_id=?",
            (case_id, self.database.deployment_instance_id),
        ).fetchall()
        for row in rows:
            if str(row[0]) not in formal_ids:
                connection.execute(
                    "DELETE FROM task_records WHERE task_id=? AND deployment_instance_id=?",
                    (row[0], self.database.deployment_instance_id),
                )

    def _delete_temporary_assets(self, connection: Any, case_id: str) -> None:
        connection.execute(
            "DELETE FROM archive_assets WHERE case_id=? AND asset_kind='staging' AND status='temporary'",
            (case_id,),
        )

    def _delete_plans(self, connection: Any, case_id: str) -> None:
        connection.execute(
            "DELETE FROM archive_plans WHERE case_id=? AND plan_id NOT IN ("
            "SELECT plan_id FROM archive_assets WHERE case_id=? AND plan_id IS NOT NULL "
            "AND status IN ('published','verified'))",
            (case_id, case_id),
        )

    def _compact_sources(self, connection: Any, case_id: str, attempts: set[str], now: str) -> None:
        formal_sources = set()
        for attempt_id in attempts:
            row = connection.execute(
                "SELECT source_id FROM archive_attempts WHERE attempt_id=? AND case_id=? AND deployment_instance_id=?",
                (attempt_id, case_id, self.database.deployment_instance_id),
            ).fetchone()
            if row is not None:
                formal_sources.add(str(row[0]))
        for row in connection.execute(
            "SELECT source_id FROM archive_publish_intents WHERE case_id=? AND deployment_instance_id=? "
            "UNION SELECT source_id FROM archive_publish_fences WHERE case_id=? AND deployment_instance_id=?",
            (case_id, self.database.deployment_instance_id, case_id, self.database.deployment_instance_id),
        ).fetchall():
            formal_sources.add(str(row[0]))
        for row in connection.execute(
            "SELECT source_id FROM source_records WHERE case_id=? AND deployment_instance_id=?",
            (case_id, self.database.deployment_instance_id),
        ).fetchall():
            source_id = str(row[0])
            if source_id in formal_sources:
                connection.execute(
                    "UPDATE source_records SET task_id=NULL,source_type=NULL,internal_path=NULL,allowed_root=NULL,"
                    "allowed_root_id=NULL,metadata_json='{}',fingerprint_json='{}',access_status='invalid',"
                    "requires_reselection=0,revalidation_error_code='RETENTION_SOURCE_TOMBSTONED',last_verified_at=NULL,"
                    "tombstone_state='tombstoned',tombstoned_at=?,tombstone_revision=tombstone_revision+1,"
                    "revision=revision+1,updated_at=? WHERE source_id=? AND deployment_instance_id=?",
                    (now, now, source_id, self.database.deployment_instance_id),
                )
            else:
                connection.execute("DELETE FROM source_records WHERE source_id=?", (source_id,))


def _id_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        raise WorkbenchPersistenceError("RETENTION_SNAPSHOT_OWNERSHIP_UNKNOWN")
    result = {identifier(item) for item in value}
    if len(result) != len(value):
        raise WorkbenchPersistenceError("RETENTION_SNAPSHOT_OWNERSHIP_UNKNOWN")
    return result
