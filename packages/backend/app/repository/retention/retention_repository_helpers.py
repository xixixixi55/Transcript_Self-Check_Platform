"""保留仓储共享的验证和安全投影。"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

from ..workbench.workbench_database import normalize_utc_z
from ..workbench.workbench_errors import WorkbenchPersistenceError
from ..workbench.workbench_serialization import validate_opaque_id, validate_safe_string


def optional_time(value: Any) -> str | None:
    return None if value is None else normalize_utc_z(value)


def required_time(value: Any) -> str:
    return normalize_utc_z(value)


def identifier(value: Any) -> str:
    return validate_opaque_id(value)


def relative_path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value or value.startswith("/"):
        raise WorkbenchPersistenceError("ABSOLUTE_PATH_FORBIDDEN")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise WorkbenchPersistenceError("ABSOLUTE_PATH_FORBIDDEN")
    return "/".join(path.parts)


def text(value: Any, code: str = "INVALID_RETENTION_RECORD") -> str:
    return validate_safe_string(value, code)


def mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise WorkbenchPersistenceError("INVALID_RETENTION_RECORD")
    return dict(value)
