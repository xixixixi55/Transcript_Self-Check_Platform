"""用于旧版读取和规范阶段 5 写入的 UTC 时间戳辅助函数。"""

from __future__ import annotations

from datetime import datetime, timezone

from .workbench_errors import WorkbenchPersistenceError


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_now_z() -> str:
    """返回规范 Z 格式的新持久 UTC 时间戳。"""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_utc(value: str | None) -> str:
    if value is None:
        return utc_now()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("naive timestamp")
        return parsed.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError) as error:
        raise WorkbenchPersistenceError("UTC_TIMESTAMP_REQUIRED") from error


def normalize_optional_utc(value: str | None) -> str | None:
    return None if value is None else normalize_utc(value)


def normalize_utc_z(value: str | None) -> str:
    """将带时区时间戳规范化为 UTC Z 格式，不重写历史。"""
    if value is None:
        return utc_now_z()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("naive timestamp")
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError) as error:
        raise WorkbenchPersistenceError("UTC_TIMESTAMP_REQUIRED") from error
