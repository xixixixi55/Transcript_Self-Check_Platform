"""Detached, case-scoped projections for inspector library records."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def project_case_inspector_snapshot(
    value: Any, *, snapshot_id: str, selected_order: int,
) -> dict[str, Any]:
    """Copy library or parser values into a detached, case-scoped inspector snapshot."""
    raw = dict(value) if isinstance(value, Mapping) else {
        "id": value.id, "name": value.name, "unit": value.unit,
        "police_number": value.police_number,
    }
    snapshot = {
        "snapshot_id": snapshot_id,
        "name": str(raw.get("name", "")),
        "unit": str(raw.get("unit", "")),
        "police_number": str(raw.get("police_number", raw.get("badge_number", ""))),
        "selected_order": selected_order,
    }
    inspector_id = raw.get("inspector_id", raw.get("id"))
    if isinstance(inspector_id, str) and inspector_id.strip():
        snapshot["inspector_id"] = inspector_id.strip()
    for key in ("captured_at", "source_version"):
        if isinstance(raw.get(key), str) and raw[key].strip():
            snapshot[key] = raw[key]
    return snapshot
