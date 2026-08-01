"""Validation helpers for durable task records."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .workbench_errors import WorkbenchPersistenceError
from .workbench_serialization import validate_opaque_id, validate_safe_string


def validate_progress(value: Any) -> None:
    if value is not None and (
        isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 100
    ):
        raise WorkbenchPersistenceError("INVALID_TASK_PROGRESS")


def counter_map(value: Any) -> dict[str, int | float]:
    if not isinstance(value, Mapping) or any(
        not isinstance(k, str) or isinstance(v, bool) or not isinstance(v, (int, float))
        for k, v in value.items()
    ):
        raise WorkbenchPersistenceError("INVALID_TASK_PROGRESS")
    return dict(value)


def process_binding(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) - {"process_tree_id", "staging_asset_id"}:
        raise WorkbenchPersistenceError("INVALID_TASK_RECORD")
    if value.get("process_tree_id") is None and value.get("staging_asset_id") is None:
        raise WorkbenchPersistenceError("INVALID_TASK_RECORD")
    if value.get("process_tree_id") is not None:
        validate_opaque_id(value.get("process_tree_id"))
    if value.get("staging_asset_id") is not None:
        validate_opaque_id(value.get("staging_asset_id"))
    return dict(value)


def validate_error_fields(code: Any, summary: Any) -> None:
    if code is not None:
        validate_safe_string(code, "INVALID_TASK_RECORD")
    if summary is not None:
        validate_safe_string(summary, "INVALID_TASK_RECORD")


def non_negative_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise WorkbenchPersistenceError("INVALID_TASK_RECORD")
    return value
