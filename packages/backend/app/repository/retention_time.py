"""后续保留服务共享的纯 UTC 和到期规则。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .workbench_constants import (
    RETENTION_FUTURE_CLOCK_SKEW_SECONDS,
    RETENTION_MAX_DAYS,
    RETENTION_MIN_DAYS,
)
from .workbench_errors import WorkbenchPersistenceError


def trusted_utc_timestamp(value: str, *, now: datetime | None = None) -> str:
    """规范化带时区的 UTC 值，并拒绝过大的未来偏差。"""
    parsed = _parse_utc(value)
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        raise WorkbenchPersistenceError("RETENTION_TIME_INVALID")
    reference = reference.astimezone(timezone.utc)
    if parsed > reference + timedelta(seconds=RETENTION_FUTURE_CLOCK_SKEW_SECONDS):
        raise WorkbenchPersistenceError("RETENTION_TIME_IN_FUTURE")
    return parsed.isoformat().replace("+00:00", "Z")


def expires_at_utc(
    anchor: str, retention_days: int, *, now: datetime | None = None
) -> str:
    """根据带时区的 UTC 锚点计算连续小时到期时间。"""
    if isinstance(retention_days, bool) or not isinstance(retention_days, int):
        raise WorkbenchPersistenceError("INVALID_RETENTION_DAYS")
    if not RETENTION_MIN_DAYS <= retention_days <= RETENTION_MAX_DAYS:
        raise WorkbenchPersistenceError("INVALID_RETENTION_DAYS")
    normalized_anchor = trusted_utc_timestamp(anchor, now=now)
    return (_parse_utc(normalized_anchor) + timedelta(days=retention_days)).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("naive timestamp")
        return parsed.astimezone(timezone.utc)
    except (AttributeError, TypeError, ValueError) as error:
        raise WorkbenchPersistenceError("RETENTION_TIME_INVALID") from error
