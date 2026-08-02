"""Pure deployment retention configuration parsing.

This module does not start a scheduler or execute cleanup. Invalid input is
reported as invalid and is never returned as an enforceable configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping

from .workbench_constants import (
    DEFAULT_RETENTION_DAYS,
    RETENTION_CONFIG_BATCH_SIZE_KEY,
    RETENTION_CONFIG_DAYS_KEY,
    RETENTION_CONFIG_MODE_KEY,
    RETENTION_CONFIG_SCAN_INTERVAL_KEY,
    RETENTION_CONFIG_KEY,
    RETENTION_DEFAULT_BATCH_SIZE,
    RETENTION_DEFAULT_SCAN_INTERVAL_SECONDS,
    RETENTION_MAX_BATCH_SIZE,
    RETENTION_MAX_DAYS,
    RETENTION_MIN_BATCH_SIZE,
    RETENTION_MIN_DAYS,
    RETENTION_MIN_SCAN_INTERVAL_SECONDS,
    RETENTION_POLICY_MODES,
)


@dataclass(frozen=True)
class RetentionPolicyConfig:
    mode: str
    retention_days: int
    scan_interval_seconds: int
    batch_size: int
    valid: bool
    diagnostic_code: str | None
    used_legacy_days: bool


def parse_retention_environment(
    environ: Mapping[str, str],
    *,
    legacy_days: str | None = None,
    allow_legacy_days: bool = False,
) -> RetentionPolicyConfig:
    """Parse deployment inputs without reading process state or starting work."""
    mode = environ.get(RETENTION_CONFIG_MODE_KEY, "disabled")
    days_value = environ.get(RETENTION_CONFIG_DAYS_KEY)
    used_legacy_days = False
    diagnostic: str | None = None
    valid = True

    if mode not in RETENTION_POLICY_MODES:
        mode = "disabled"
        valid = False
        diagnostic = "RETENTION_CONFIG_INVALID_MODE"

    if days_value is None and allow_legacy_days:
        days_value = legacy_days
        used_legacy_days = legacy_days is not None
    days, days_ok = _bounded_int(days_value, RETENTION_MIN_DAYS, RETENTION_MAX_DAYS, DEFAULT_RETENTION_DAYS)
    if days_value is not None and not days_ok:
        valid = False
        diagnostic = diagnostic or (
            "RETENTION_CONFIG_INVALID_LEGACY_DAYS"
            if used_legacy_days else "RETENTION_CONFIG_INVALID_DAYS"
        )

    interval, interval_ok = _bounded_int(
        environ.get(RETENTION_CONFIG_SCAN_INTERVAL_KEY),
        RETENTION_MIN_SCAN_INTERVAL_SECONDS,
        2**31 - 1,
        RETENTION_DEFAULT_SCAN_INTERVAL_SECONDS,
    )
    if environ.get(RETENTION_CONFIG_SCAN_INTERVAL_KEY) is not None and not interval_ok:
        valid = False
        diagnostic = diagnostic or "RETENTION_CONFIG_INVALID_SCAN_INTERVAL"

    batch, batch_ok = _bounded_int(
        environ.get(RETENTION_CONFIG_BATCH_SIZE_KEY),
        RETENTION_MIN_BATCH_SIZE,
        RETENTION_MAX_BATCH_SIZE,
        RETENTION_DEFAULT_BATCH_SIZE,
    )
    if environ.get(RETENTION_CONFIG_BATCH_SIZE_KEY) is not None and not batch_ok:
        valid = False
        diagnostic = diagnostic or "RETENTION_CONFIG_INVALID_BATCH_SIZE"

    if not valid:
        mode = "disabled"
    return RetentionPolicyConfig(
        mode=mode,
        retention_days=days,
        scan_interval_seconds=interval,
        batch_size=batch,
        valid=valid,
        diagnostic_code=diagnostic,
        used_legacy_days=used_legacy_days,
    )


def legacy_retention_days(environ: Mapping[str, str]) -> str | None:
    """Return the compatibility value without making it executable."""
    return environ.get(RETENTION_CONFIG_KEY)


def _bounded_int(value: str | None, minimum: int, maximum: int, default: int) -> tuple[int, bool]:
    if value is None:
        return default, True
    try:
        parsed = int(value, 10)
    except (TypeError, ValueError):
        return default, False
    return (parsed, True) if minimum <= parsed <= maximum else (default, False)
