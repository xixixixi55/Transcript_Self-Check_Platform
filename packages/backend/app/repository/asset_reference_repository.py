"""不透明资产引用注册表；内容保留在 SQLite 之外。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .workbench_database import WorkbenchDatabase, utc_now
from .workbench_errors import WorkbenchPersistenceError
from .workbench_repository_helpers import json_text, row_json
from .workbench_serialization import validate_opaque_asset_refs, validate_opaque_id, validate_safe_string


class AssetReferenceRepository:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database

    def create(self, reference: Mapping[str, Any]) -> dict[str, Any]:
        refs = validate_opaque_asset_refs([{key: reference[key] for key in ("asset_id", "asset_kind", "fingerprint", "metadata") if key in reference}])
        asset_id = refs[0]["asset_id"]
        case_id = validate_opaque_id(reference.get("case_id"))
        fingerprint = reference.get("fingerprint")
        if fingerprint is not None and not isinstance(fingerprint, str):
            raise WorkbenchPersistenceError("INVALID_ASSET_REFERENCE")
        status = validate_safe_string(reference.get("status", "available"), "INVALID_ASSET_REFERENCE")
        now = utc_now()
        values = (
            asset_id, case_id, reference["asset_kind"], fingerprint,
            json_text(reference.get("metadata", {})), status, now,
        )
        with self.database.transaction() as connection:
            try:
                connection.execute(
                    "INSERT INTO asset_references(asset_id, case_id, asset_kind, fingerprint, metadata_json, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    values,
                )
            except Exception as error:
                raise WorkbenchPersistenceError("ASSET_REFERENCE_CREATE_FAILED") from error
        return {**refs[0], "case_id": case_id, "status": values[5], "created_at": now}

    def get(self, asset_id: str) -> dict[str, Any]:
        asset_id = validate_opaque_id(asset_id)
        connection = self.database.connect()
        try:
            row = connection.execute("SELECT * FROM asset_references WHERE asset_id = ?", (asset_id,)).fetchone()
        finally:
            connection.close()
        if row is None:
            raise WorkbenchPersistenceError("ASSET_REFERENCE_NOT_FOUND")
        return {
            "asset_id": row["asset_id"], "case_id": row["case_id"], "asset_kind": row["asset_kind"],
            "fingerprint": row["fingerprint"], "metadata": row_json(row, "metadata_json"),
            "status": row["status"], "created_at": row["created_at"],
        }

    def list_case(self, case_id: str, asset_kind: str | None = None) -> list[dict[str, Any]]:
        case_id = validate_opaque_id(case_id)
        connection = self.database.connect()
        try:
            if asset_kind is None:
                rows = connection.execute(
                    "SELECT * FROM asset_references WHERE case_id = ? ORDER BY created_at, asset_id",
                    (case_id,),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM asset_references WHERE case_id = ? AND asset_kind = ? ORDER BY created_at, asset_id",
                    (case_id, asset_kind),
                ).fetchall()
        finally:
            connection.close()
        return [_reference_dict(row) for row in rows]

    def delete(self, case_id: str, asset_id: str) -> None:
        case_id = validate_opaque_id(case_id)
        asset_id = validate_opaque_id(asset_id)
        with self.database.transaction() as connection:
            connection.execute(
                "DELETE FROM asset_references WHERE case_id = ? AND asset_id = ?",
                (case_id, asset_id),
            )


def _reference_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "asset_id": row["asset_id"], "case_id": row["case_id"], "asset_kind": row["asset_kind"],
        "fingerprint": row["fingerprint"], "metadata": row_json(row, "metadata_json"),
        "status": row["status"], "created_at": row["created_at"],
    }
