"""Small repository helpers shared by the SQLite workbench repositories."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .workbench_database import utc_now
from .workbench_errors import WorkbenchPersistenceError
from .workbench_serialization import dump_bounded_json, load_bounded_json, validate_safe_string


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


def case_shell_values(
    shell: Mapping[str, Any], metadata: Mapping[str, Any] | None,
) -> tuple[Any, Any, Any]:
    """Fill only blank shell labels from parser metadata."""
    values = [shell["case_number"], shell["case_name"], shell["case_summary"]]
    incoming = metadata if metadata is not None else {}
    if not isinstance(incoming, Mapping):
        raise WorkbenchPersistenceError("INVALID_CASE_SHELL")
    for index, key in enumerate(("case_number", "case_name", "case_summary")):
        candidate = incoming.get(key)
        if candidate is not None:
            candidate = validate_safe_string(candidate, "INVALID_CASE_SHELL")
        if not str(values[index] or "").strip() and candidate:
            values[index] = candidate
    return tuple(values)


def optional_safe(value: Any, code: str) -> str | None:
    return None if value is None else validate_safe_string(value, code)


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
        "revalidation_error_code": row["revalidation_error_code"],
        "last_verified_at": row["last_verified_at"],
        "revision": int(row["revision"]),
    }
