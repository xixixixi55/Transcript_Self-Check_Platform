"""任务绑定密封执行输入的持久所有权和状态。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .workbench_database import WorkbenchDatabase, utc_now
from .workbench_errors import WorkbenchPersistenceError
from .workbench_serialization import validate_opaque_id


class ArchiveInputSnapshotRepository:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database

    def create_copying(self, value: Mapping[str, Any]) -> dict[str, Any]:
        required = (
            "snapshot_id", "task_id", "attempt_id", "case_id", "source_id",
            "source_revision", "draft_revision", "source_root_id",
            "snapshot_root_id", "snapshot_locator", "marker_token",
        )
        if any(key not in value for key in required):
            raise WorkbenchPersistenceError("ARCHIVE_INPUT_SNAPSHOT_INVALID")
        ids = {key: validate_opaque_id(value[key]) for key in (
            "snapshot_id", "task_id", "attempt_id", "case_id", "source_id",
            "source_root_id", "snapshot_root_id", "marker_token",
        )}
        for key in ("snapshot_locator",):
            if not isinstance(value[key], str) or not value[key] or ".." in value[key].replace("\\", "/").split("/"):
                raise WorkbenchPersistenceError("ARCHIVE_INPUT_SNAPSHOT_INVALID")
        now = utc_now()
        with self.database.transaction() as connection:
            task = connection.execute(
                "SELECT case_id, deployment_instance_id, status FROM task_records "
                "WHERE task_id=? AND kind='archive' AND deployment_instance_id=?",
                (ids["task_id"], self.database.deployment_instance_id),
            ).fetchone()
            attempt = connection.execute(
                "SELECT task_id, deployment_instance_id, case_id, source_id, "
                "source_revision, draft_revision, status FROM archive_attempts "
                "WHERE attempt_id=? AND deployment_instance_id=?",
                (ids["attempt_id"], self.database.deployment_instance_id),
            ).fetchone()
            if (
                task is None or attempt is None
                or task["case_id"] != ids["case_id"]
                or task["deployment_instance_id"] != self.database.deployment_instance_id
                or attempt["task_id"] != ids["task_id"]
                or attempt["deployment_instance_id"] != self.database.deployment_instance_id
                or attempt["case_id"] != ids["case_id"]
                or attempt["source_id"] != ids["source_id"]
                or int(attempt["source_revision"] or 0) != int(value["source_revision"])
                or int(attempt["draft_revision"] or 0) != int(value["draft_revision"])
                or attempt["status"] not in {"accepted", "running"}
            ):
                raise WorkbenchPersistenceError("ARCHIVE_INPUT_SNAPSHOT_BINDING_MISMATCH")
            try:
                connection.execute(
                    "INSERT INTO archive_input_snapshots(snapshot_id, task_id, attempt_id, "
                    "deployment_instance_id, case_id, source_id, source_revision, draft_revision, "
                    "source_root_id, snapshot_root_id, snapshot_locator, manifest_json, "
                    "input_fingerprint, status, marker_token, created_at, sealed_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'copying', ?, ?, NULL, ?)",
                    (ids["snapshot_id"], ids["task_id"], ids["attempt_id"],
                     self.database.deployment_instance_id, ids["case_id"], ids["source_id"],
                     int(value["source_revision"]), int(value["draft_revision"]),
                     ids["source_root_id"], ids["snapshot_root_id"], value["snapshot_locator"],
                     "{}", "", ids["marker_token"], now, now),
                )
            except Exception as error:
                raise WorkbenchPersistenceError("ARCHIVE_INPUT_SNAPSHOT_CONFLICT") from error
        return self.get(ids["snapshot_id"])

    def seal(
        self, snapshot_id: str, *, manifest: list[dict[str, Any]],
        input_fingerprint: str,
    ) -> dict[str, Any]:
        snapshot_id = validate_opaque_id(snapshot_id)
        serialized = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        now = utc_now()
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM archive_input_snapshots WHERE snapshot_id=? "
                "AND deployment_instance_id=?",
                (snapshot_id, self.database.deployment_instance_id),
            ).fetchone()
            if row is None or row["deployment_instance_id"] != self.database.deployment_instance_id:
                raise WorkbenchPersistenceError("ARCHIVE_INPUT_SNAPSHOT_NOT_FOUND")
            if row["status"] == "sealed":
                if row["input_fingerprint"] != input_fingerprint or row["manifest_json"] != serialized:
                    raise WorkbenchPersistenceError("ARCHIVE_INPUT_SNAPSHOT_CONFLICT")
                return dict(row)
            if row["status"] != "copying":
                raise WorkbenchPersistenceError("ARCHIVE_INPUT_SNAPSHOT_STATE_INVALID")
            if connection.execute(
                "UPDATE archive_input_snapshots SET manifest_json=?, input_fingerprint=?, "
                "status='sealed', sealed_at=?, updated_at=? WHERE snapshot_id=? "
                "AND deployment_instance_id=? AND status='copying'",
                (serialized, input_fingerprint, now, now, snapshot_id,
                 self.database.deployment_instance_id),
            ).rowcount != 1:
                raise WorkbenchPersistenceError("ARCHIVE_INPUT_SNAPSHOT_STATE_INVALID")
            if connection.execute(
                "UPDATE archive_attempts SET input_snapshot_id=?, input_snapshot_root_id=?, "
                "input_snapshot_locator=?, input_snapshot_fingerprint=?, input_snapshot_status='sealed', "
                "revision=revision+1 WHERE attempt_id=? AND task_id=? AND deployment_instance_id=? "
                "AND status IN ('accepted','running')",
                (row["snapshot_id"], row["snapshot_root_id"], row["snapshot_locator"],
                 input_fingerprint, row["attempt_id"], row["task_id"],
                 self.database.deployment_instance_id),
            ).rowcount != 1:
                raise WorkbenchPersistenceError("ARCHIVE_INPUT_SNAPSHOT_BINDING_MISMATCH")
            result = connection.execute(
                "SELECT * FROM archive_input_snapshots WHERE snapshot_id=? "
                "AND deployment_instance_id=?",
                (snapshot_id, self.database.deployment_instance_id),
            ).fetchone()
        return dict(result)

    def mark_invalidated(self, snapshot_id: str) -> None:
        self._set_status(snapshot_id, {"copying", "sealed"}, "invalidated")

    def mark_cleaned(self, snapshot_id: str) -> None:
        self._set_status(snapshot_id, {"copying", "invalidated", "sealed"}, "cleaned")

    def get(self, snapshot_id: str) -> dict[str, Any]:
        snapshot_id = validate_opaque_id(snapshot_id)
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM archive_input_snapshots WHERE snapshot_id=? AND deployment_instance_id=?",
                (snapshot_id, self.database.deployment_instance_id),
            ).fetchone()
        if row is None:
            raise WorkbenchPersistenceError("ARCHIVE_INPUT_SNAPSHOT_NOT_FOUND")
        return dict(row)

    def list_unfinished(self) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM archive_input_snapshots WHERE deployment_instance_id=? "
                "AND status IN ('copying','invalidated') ORDER BY created_at,snapshot_id",
                (self.database.deployment_instance_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _set_status(self, snapshot_id: str, allowed: set[str], target: str) -> None:
        snapshot_id = validate_opaque_id(snapshot_id)
        placeholders = ",".join("?" for _ in allowed)
        with self.database.transaction() as connection:
            updated = connection.execute(
                f"UPDATE archive_input_snapshots SET status=?, updated_at=? WHERE snapshot_id=? "
                f"AND deployment_instance_id=? AND status IN ({placeholders})",
                (target, utc_now(), snapshot_id, self.database.deployment_instance_id, *allowed),
            )
            if updated.rowcount != 1:
                row = connection.execute(
                    "SELECT status FROM archive_input_snapshots WHERE snapshot_id=? "
                    "AND deployment_instance_id=?",
                    (snapshot_id, self.database.deployment_instance_id),
                ).fetchone()
                if row is None:
                    raise WorkbenchPersistenceError("ARCHIVE_INPUT_SNAPSHOT_NOT_FOUND")
                if row["status"] != target:
                    raise WorkbenchPersistenceError("ARCHIVE_INPUT_SNAPSHOT_STATE_INVALID")
