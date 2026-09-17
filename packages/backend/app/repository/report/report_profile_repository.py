"""Layer 20：版本化 ReportProfile 持久化，不保存报告字段原值。"""

from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

from ..workbench.workbench_database import WorkbenchDatabase, utc_now
from ..workbench.workbench_errors import WorkbenchPersistenceError
from ..workbench.workbench_serialization import validate_opaque_id

REPORT_PROFILE_ADAPTER_ID = "report-profile-v1"
REPORT_PROFILE_ADAPTER_VERSION = "1.1.0"
_ALLOWED_MAPPING_KEYS = {
    "canonical_field", "source_file", "json_path", "collection_path", "value_type",
    "normalizers", "required", "confidence", "evidence", "confirmation",
}


class ReportProfileRepository:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database

    def save_confirmed(
        self,
        *,
        profile_id: str,
        display_name: str,
        structure_fingerprint: str,
        mappings: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        profile_id = validate_opaque_id(profile_id)
        name = str(display_name).strip()
        fingerprint = str(structure_fingerprint).strip()
        safe_mappings = _validate_mappings(mappings)
        if not name or len(name) > 120 or not fingerprint or not safe_mappings:
            raise WorkbenchPersistenceError("REPORT_PROFILE_INVALID")
        now = utc_now()
        with self.database.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM report_profiles "
                "WHERE structure_fingerprint=? AND status='confirmed'",
                (fingerprint,),
            ).fetchone()
            if existing is not None:
                existing_profile = _row(existing)
                if (
                    existing_profile["display_name"] != name
                    or existing_profile["mappings"] != safe_mappings
                ):
                    raise WorkbenchPersistenceError("REPORT_PROFILE_CONFLICT")
                return existing_profile
            version = int(connection.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM report_profiles WHERE profile_id=?",
                (profile_id,),
            ).fetchone()[0])
            try:
                connection.execute(
                    "INSERT INTO report_profiles(profile_id,version,schema_version,display_name,"
                    "structure_fingerprint,adapter_id,adapter_version,status,mappings_json,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        profile_id, version, 1, name, fingerprint,
                        REPORT_PROFILE_ADAPTER_ID, REPORT_PROFILE_ADAPTER_VERSION,
                        "confirmed", json.dumps(safe_mappings, ensure_ascii=False, separators=(",", ":")),
                        now, now,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise WorkbenchPersistenceError("REPORT_PROFILE_CONFLICT") from error
        return self.get(profile_id, version)

    def find_confirmed(self, structure_fingerprint: str) -> dict[str, Any] | None:
        connection = self.database.connect()
        try:
            row = connection.execute(
                "SELECT * FROM report_profiles WHERE structure_fingerprint=? "
                "AND status='confirmed'",
                (structure_fingerprint,),
            ).fetchone()
        finally:
            connection.close()
        return None if row is None else _row(row)

    def get(self, profile_id: str, version: int | None = None) -> dict[str, Any]:
        profile_id = validate_opaque_id(profile_id)
        connection = self.database.connect()
        try:
            if version is None:
                row = connection.execute(
                    "SELECT * FROM report_profiles WHERE profile_id=? ORDER BY version DESC LIMIT 1",
                    (profile_id,),
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT * FROM report_profiles WHERE profile_id=? AND version=?",
                    (profile_id, version),
                ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise WorkbenchPersistenceError("REPORT_PROFILE_NOT_FOUND")
        return _row(row)


def _validate_mappings(value: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(value, (str, bytes)) or len(value) > 32:
        raise WorkbenchPersistenceError("REPORT_PROFILE_INVALID")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping) or set(item) - _ALLOWED_MAPPING_KEYS:
            raise WorkbenchPersistenceError("REPORT_PROFILE_INVALID")
        canonical = str(item.get("canonical_field", ""))
        source_file = str(item.get("source_file", ""))
        normalized_source_file = source_file.replace("\\", "/")
        json_path = str(item.get("json_path", ""))
        collection_path = str(item.get("collection_path", ""))
        try:
            confidence = float(item.get("confidence", 0))
        except (TypeError, ValueError) as error:
            raise WorkbenchPersistenceError("REPORT_PROFILE_INVALID") from error
        if (
            not canonical or canonical in seen or not source_file or not json_path
            or PurePosixPath(normalized_source_file).is_absolute()
            or PureWindowsPath(source_file).is_absolute()
            or bool(PureWindowsPath(source_file).drive)
            or ".." in PurePosixPath(normalized_source_file).parts
            or not json_path.startswith("$")
            or collection_path != _collection_path_for_json_path(json_path, canonical)
            or not math.isfinite(confidence)
        ):
            raise WorkbenchPersistenceError("REPORT_PROFILE_INVALID")
        seen.add(canonical)
        result.append({
            "canonical_field": canonical,
            "source_file": normalized_source_file,
            "json_path": json_path,
            "collection_path": collection_path,
            "value_type": str(item.get("value_type", "string")),
            "normalizers": [str(entry) for entry in item.get("normalizers", ["trim"])],
            "required": bool(item.get("required", False)),
            "confidence": confidence,
            "evidence": [str(entry) for entry in item.get("evidence", [])][:4],
            "confirmation": "user_confirmed",
        })
    return sorted(
        result,
        key=lambda item: (
            item["canonical_field"], item["source_file"], item["json_path"],
        ),
    )


def _collection_path_for_json_path(json_path: str, canonical_field: str) -> str:
    tokens = json_path[2:].split("/") if json_path.startswith("$/") else []
    wildcard = max((index for index, token in enumerate(tokens) if token == "*"), default=-1)
    if wildcard >= 0:
        return "$/" + "/".join(tokens[:wildcard + 1])
    if canonical_field.startswith("material.") and tokens:
        return "$" if len(tokens) == 1 else "$/" + "/".join(tokens[:-1])
    return "$"


def _row(row: Mapping[str, Any]) -> dict[str, Any]:
    mappings = json.loads(str(row["mappings_json"]))
    return {
        "profile_id": str(row["profile_id"]),
        "version": int(row["version"]),
        "schema_version": int(row["schema_version"]),
        "display_name": str(row["display_name"]),
        "structure_fingerprint": str(row["structure_fingerprint"]),
        "adapter_id": str(row["adapter_id"]),
        "adapter_version": str(row["adapter_version"]),
        "status": str(row["status"]),
        "mappings": mappings,
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


__all__ = [
    "REPORT_PROFILE_ADAPTER_ID", "REPORT_PROFILE_ADAPTER_VERSION",
    "ReportProfileRepository",
]
