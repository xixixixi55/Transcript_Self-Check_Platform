"""Case-scoped field source and confirmation-state coordination."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

from ..repository.workbench_database import utc_now

_SOURCE_VALUES = {"report", "user", "system_default"}
_CONFIRMATION_VALUES = {"confirmed", "pending"}
_STABLE_FIELDS = {"evidence_id", "snapshot_id", "inspector_id", "id", "selected_order"}
_PERSISTED_CONTROL_FIELDS = {"introduction.evidence_list.completeness"}


class FieldProvenanceService:
    """Initialize and preserve field state without leaking it into Legacy DTO output."""

    def initialize(
        self, report: Mapping[str, Any], initial_states: Mapping[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        provided = initial_states or {}
        now = utc_now()
        return {
            entry["field_path"]: _state(entry, _initial_state(entry, provided), now)
            for entry in _entries(report)
        }

    def reconcile(
        self,
        previous_report: Mapping[str, Any], previous_states: Mapping[str, Any],
        report: Mapping[str, Any], submitted_states: Mapping[str, Any] | None,
    ) -> dict[str, dict[str, Any]]:
        old_values = {entry["field_path"]: entry["value"] for entry in _entries(previous_report)}
        provided = submitted_states or {}
        now = utc_now()
        states: dict[str, dict[str, Any]] = {}
        for entry in _entries(report):
            path = entry["field_path"]
            previous = previous_states.get(path)
            state = _state(entry, provided.get(path, previous), now)
            if path not in old_values or old_values[path] != entry["value"]:
                state["source"] = "user"
                state["revision"] = int(previous.get("revision", 0)) + 1 if isinstance(previous, Mapping) else 1
                state["last_changed_at"] = now
            states[path] = state
        for path in _PERSISTED_CONTROL_FIELDS:
            raw = provided.get(path, previous_states.get(path))
            if raw is not None:
                states[path] = _state(
                    {"field_path": path, "value": None, "subject_id": None}, raw, now,
                )
        return states


def _entries(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    _walk(report, (), items)
    if not any(item["field_path"] == "introduction.inspectors" for item in items):
        introduction = report.get("introduction")
        if isinstance(introduction, Mapping):
            snapshots = introduction.get("inspector_snapshots", introduction.get("inspectors", []))
            _add(items, "introduction.inspectors", snapshots, None)
    return items


def _walk(value: Any, path: tuple[str, ...], items: list[dict[str, Any]]) -> None:
    if path == ("introduction", "evidence_list"):
        _evidence_entries(value, items)
        return
    if path == ("introduction", "inspector_snapshots"):
        _snapshot_entries(value, items)
        return
    if path == ("introduction", "inspectors"):
        return
    if path == ("attachments", "photo_groups"):
        _photo_group_entries(value, items)
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if isinstance(key, str):
                _walk(child, (*path, key), items)
        return
    if isinstance(value, list):
        _add(items, ".".join(path), value, None)
        return
    _add(items, ".".join(path), value, None)


def _evidence_entries(value: Any, items: list[dict[str, Any]]) -> None:
    for evidence in value if isinstance(value, list) else ():
        if not isinstance(evidence, Mapping):
            continue
        identifier = str(evidence.get("evidence_id", "")).strip()
        if not identifier:
            continue
        for key, child in evidence.items():
            if key not in _STABLE_FIELDS and isinstance(key, str):
                _add(items, f"evidence.{identifier}.{key}", child, identifier)


def _snapshot_entries(value: Any, items: list[dict[str, Any]]) -> None:
    snapshots = value if isinstance(value, list) else ()
    _add(items, "introduction.inspectors", snapshots, None)
    for snapshot in snapshots:
        if not isinstance(snapshot, Mapping):
            continue
        identifier = str(snapshot.get("snapshot_id", "")).strip()
        if not identifier:
            continue
        for key in ("name", "unit", "position", "police_number"):
            _add(items, f"inspectors.{identifier}.{key}", snapshot.get(key, ""), identifier)


def _photo_group_entries(value: Any, items: list[dict[str, Any]]) -> None:
    for group in value if isinstance(value, list) else ():
        if isinstance(group, Mapping) and isinstance(group.get("material_id"), str) and group["material_id"]:
            _add(items, f"photo_groups.{group['material_id']}", dict(group), group["material_id"])


def _add(items: list[dict[str, Any]], path: str, value: Any, subject_id: str | None) -> None:
    if path:
        items.append({"field_path": path, "value": copy.deepcopy(value), "subject_id": subject_id})


def _state(entry: Mapping[str, Any], raw: Any, now: str) -> dict[str, Any]:
    state = dict(raw) if isinstance(raw, Mapping) else {}
    value = entry["value"]
    state.update({
        "field_path": entry["field_path"],
        "source": state.get("source") if state.get("source") in _SOURCE_VALUES else _initial_source(value),
        "confirmation": state.get("confirmation") if state.get("confirmation") in _CONFIRMATION_VALUES else _confirmation(value),
        "revision": state.get("revision") if isinstance(state.get("revision"), int) and not isinstance(state.get("revision"), bool) and state["revision"] >= 0 else 0,
        "last_changed_at": state.get("last_changed_at") if isinstance(state.get("last_changed_at"), str) else now,
    })
    if entry["subject_id"]:
        state["subject_id"] = entry["subject_id"]
    else:
        state.pop("subject_id", None)
    return state


def _initial_state(entry: Mapping[str, Any], provided: Mapping[str, Any]) -> Any:
    path = entry["field_path"]
    direct = provided.get(path)
    if direct is not None or not path.startswith("inspectors."):
        return direct
    return provided.get("introduction.inspectors")


def _initial_source(value: Any) -> str:
    return "report" if _has_value(value) else "system_default"


def _confirmation(value: Any) -> str:
    return "confirmed" if _has_value(value) else "pending"


def _has_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    return value is not None and value != [] and value != {}
