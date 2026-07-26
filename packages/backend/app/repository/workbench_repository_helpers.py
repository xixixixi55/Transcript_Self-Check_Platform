"""Small repository helpers shared by the SQLite workbench repositories."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .workbench_database import utc_now
from .workbench_serialization import dump_bounded_json, load_bounded_json


def value_or_none(value: Any) -> Any:
    return None if value is None else value


def bool_int(value: bool) -> int:
    return 1 if value else 0


def row_json(row: Mapping[str, Any], key: str) -> Any:
    return load_bounded_json(str(row[key]))


def json_text(value: Any) -> str:
    return dump_bounded_json(value)


def now_or(value: str | None) -> str:
    return value or utc_now()


def public_source_record(row: Mapping[str, Any]) -> dict[str, Any]:
    fingerprint = row_json(row, "fingerprint_json")
    return {
        "schema_version": int(row["schema_version"]),
        "source_id": str(row["source_id"]),
        "source_type": str(row["source_type"]),
        "case_id": str(row["case_id"]),
        "task_id": row["task_id"],
        "allowed_root_id": str(row["allowed_root_id"]),
        "metadata": row_json(row, "metadata_json"),
        "fingerprint": fingerprint.get("value", "") if isinstance(fingerprint, dict) else "",
        "access_status": str(row["access_status"]),
        "requires_reselection": bool(row["requires_reselection"]),
        "last_verified_at": row["last_verified_at"],
        "revision": int(row["revision"]),
    }
