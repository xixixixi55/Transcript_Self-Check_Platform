"""具有审慎安全公开投影的内部归档资产记录。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .workbench_database import WorkbenchDatabase, normalize_utc, utc_now
from .workbench_errors import RevisionConflictError, WorkbenchPersistenceError
from .workbench_repository_helpers import json_text, row_json
from .workbench_serialization import validate_opaque_id

_KINDS = {"staging", "rar_volume", "manifest"}
_STATUSES = {"temporary", "published", "verified", "invalid"}


class ArchiveAssetRepository:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database

    def create(self, asset: Mapping[str, Any]) -> dict[str, Any]:
        value = _asset(asset)
        with self.database.transaction() as connection:
            try:
                connection.execute(
                    "INSERT INTO archive_assets(asset_id,schema_version,case_id,task_id,plan_id,asset_kind,"
                    "status,internal_locator,metadata_json,created_at,updated_at,revision) "
                    "VALUES (?,1,?,?,?,?,?,?,?,?,?,0)",
                    (
                        value["asset_id"], value["case_id"], value["task_id"],
                        value["plan_id"], value["asset_kind"], value["status"],
                        value["internal_locator"], json_text(value["metadata"]),
                        value["created_at"], value["updated_at"],
                    ),
                )
            except Exception as error:
                raise WorkbenchPersistenceError("ARCHIVE_ASSET_CREATE_FAILED") from error
        return self.get_internal(value["asset_id"])

    def get_internal(self, asset_id: str) -> dict[str, Any]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM archive_assets WHERE asset_id=?",
                (validate_opaque_id(asset_id),),
            ).fetchone()
        if row is None:
            raise WorkbenchPersistenceError("ARCHIVE_ASSET_NOT_FOUND")
        return _asset_dict(row)

    def get_public(self, asset_id: str) -> dict[str, Any]:
        value = self.get_internal(asset_id)
        return {
            key: value[key] for key in (
                "asset_id", "case_id", "task_id", "plan_id", "asset_kind",
                "status", "created_at", "updated_at", "revision",
            )
        }

    def list_public_for_task(self, task_id: str) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT asset_id FROM archive_assets WHERE task_id=? "
                "AND status IN ('published','verified') ORDER BY created_at,asset_id",
                (validate_opaque_id(task_id),),
            ).fetchall()
        return [self.get_public(str(row["asset_id"])) for row in rows]

    def update_status(
        self, asset_id: str, status: str, expected_revision: int
    ) -> dict[str, Any]:
        if status not in _STATUSES:
            raise WorkbenchPersistenceError("INVALID_ARCHIVE_ASSET")
        current = self.get_internal(asset_id)
        if current["revision"] != expected_revision:
            raise RevisionConflictError("archive_asset", expected_revision, current["revision"])
        with self.database.transaction() as connection:
            updated = connection.execute(
                "UPDATE archive_assets SET status=?,updated_at=?,revision=revision+1 "
                "WHERE asset_id=? AND revision=?",
                (status, utc_now(), asset_id, expected_revision),
            )
            if updated.rowcount != 1:
                raise RevisionConflictError("archive_asset", expected_revision, current["revision"])
        return self.get_internal(asset_id)


def _asset(value: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result["asset_id"] = validate_opaque_id(value.get("asset_id"))
    result["case_id"] = validate_opaque_id(value.get("case_id"))
    result["task_id"] = None if value.get("task_id") is None else validate_opaque_id(value["task_id"])
    result["plan_id"] = None if value.get("plan_id") is None else validate_opaque_id(value["plan_id"])
    if value.get("asset_kind") not in _KINDS or value.get("status") not in _STATUSES:
        raise WorkbenchPersistenceError("INVALID_ARCHIVE_ASSET")
    result["internal_locator"] = value.get("internal_locator")
    if result["internal_locator"] is not None and not isinstance(result["internal_locator"], str):
        raise WorkbenchPersistenceError("INVALID_ARCHIVE_ASSET")
    metadata = value.get("metadata", {})
    if not isinstance(metadata, Mapping):
        raise WorkbenchPersistenceError("INVALID_ARCHIVE_ASSET")
    result["metadata"] = dict(metadata)
    result["created_at"] = normalize_utc(value.get("created_at"))
    result["updated_at"] = normalize_utc(value.get("updated_at"))
    return result


def _asset_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "asset_id": row["asset_id"], "schema_version": int(row["schema_version"]),
        "case_id": row["case_id"],
        "task_id": row["task_id"], "plan_id": row["plan_id"],
        "asset_kind": row["asset_kind"], "status": row["status"],
        "internal_locator": row["internal_locator"],
        "metadata": row_json(row, "metadata_json"), "created_at": row["created_at"],
        "updated_at": row["updated_at"], "revision": int(row["revision"]),
    }
