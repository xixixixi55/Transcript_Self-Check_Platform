"""UTC timestamp helpers for legacy reads and canonical Phase 5 writes."""

from __future__ import annotations

from datetime import datetime, timezone

from .workbench_errors import WorkbenchPersistenceError


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def utc_now_z() -> str:
    """Return a new durable UTC timestamp in the canonical Z form."""
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
    """Normalize an aware timestamp to canonical UTC Z without rewriting history."""
    if value is None:
        return utc_now_z()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("naive timestamp")
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError) as error:
        raise WorkbenchPersistenceError("UTC_TIMESTAMP_REQUIRED") from error
