"""Inspector management and report snapshot compatibility services."""

from __future__ import annotations

import copy
from dataclasses import asdict
from collections.abc import Iterable, Mapping
from typing import Any

from .canonical_models_service import InspectorSnapshot
from ..repository.inspector_repository import (
    InspectorDataError,
    InspectorNotFoundError,
    InspectorRecord,
    InspectorRepository,
    InspectorValidationError,
)


def _snapshot_text(value: Any) -> str:
    if value is None or isinstance(value, (dict, list, tuple, set, bool)):
        return ""
    return str(value).strip()


def inspector_to_dict(record: InspectorRecord) -> dict[str, Any]:
    return asdict(record)


def snapshots_to_legacy(snapshots: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "name": _snapshot_text(item.get("name")),
            "unit": _snapshot_text(item.get("unit")),
            "position": _snapshot_text(item.get("position")),
            "badge_number": _snapshot_text(item.get("police_number")),
        }
        for item in snapshots
    ]


def legacy_to_snapshots(inspectors: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "name": _snapshot_text(item.get("name")),
            "unit": _snapshot_text(item.get("unit")),
            "position": _snapshot_text(item.get("position")),
            "police_number": _snapshot_text(item.get("badge_number")),
        }
        for item in inspectors
    ]


def apply_inspector_snapshot_compatibility(report: Mapping[str, Any]) -> dict[str, Any]:
    """Use snapshots as authority and regenerate the legacy renderer projection."""

    result = copy.deepcopy(dict(report))
    introduction = result.setdefault("introduction", {})
    raw_snapshots = introduction.get("inspector_snapshots")
    if isinstance(raw_snapshots, list):
        snapshots = [item for item in raw_snapshots if isinstance(item, Mapping)]
    else:
        snapshots = legacy_to_snapshots(
            item for item in introduction.get("inspectors") or [] if isinstance(item, Mapping)
        )
    normalized_snapshots = [
        {
            "name": _snapshot_text(item.get("name")),
            "unit": _snapshot_text(item.get("unit")),
            "position": _snapshot_text(item.get("position")),
            "police_number": _snapshot_text(item.get("police_number")),
        }
        for item in snapshots
    ]
    introduction["inspector_snapshots"] = normalized_snapshots
    introduction["inspectors"] = snapshots_to_legacy(normalized_snapshots)
    return result


class InspectorService:
    """Business facade over the local repository and snapshot generation."""

    def __init__(self, repository: InspectorRepository | None = None):
        self.repository = repository or InspectorRepository()

    def list(self) -> list[dict[str, Any]]:
        return [inspector_to_dict(item) for item in self.repository.list()]

    def get(self, inspector_id: str) -> dict[str, Any] | None:
        record = self.repository.get(inspector_id)
        return inspector_to_dict(record) if record else None

    def create(self, name: Any, unit: Any, position: Any, police_number: Any) -> dict[str, Any]:
        return inspector_to_dict(self.repository.create(name, unit, position, police_number))

    def update(
        self, inspector_id: str, *, name: Any = None, unit: Any = None,
        position: Any = None, police_number: Any = None,
    ) -> dict[str, Any]:
        return inspector_to_dict(self.repository.update(
            inspector_id, name=name, unit=unit, position=position, police_number=police_number,
        ))

    def delete(self, inspector_id: str) -> None:
        self.repository.delete(inspector_id)

    def snapshots_from_ids(self, inspector_ids: Iterable[str]) -> list[InspectorSnapshot]:
        ids = list(inspector_ids)
        if len(ids) != len(set(ids)):
            raise ValueError("检查人员不能重复选择")
        snapshots: list[InspectorSnapshot] = []
        for order, inspector_id in enumerate(ids):
            record = self.repository.get(inspector_id)
            if record is None:
                raise InspectorNotFoundError("检查人员不存在")
            snapshots.append(
                InspectorSnapshot(
                    inspector_id=record.id,
                    name=record.name,
                    unit=record.unit,
                    position=record.position,
                    police_number=record.police_number,
                    selected_order=order,
                )
            )
        return snapshots
