"""案件级证据和检查人员顺序规范化。"""

from __future__ import annotations

import copy
import re
import secrets
from collections.abc import Callable, Mapping
from typing import Any

from ..repository.inspector_repository import project_case_inspector_snapshot

_MAX_SAFE_INTEGER = 9_007_199_254_740_991


class CaseOrderService:
    """应用一次性解析器默认顺序，并保留后续用户顺序。"""

    def __init__(self, identifier_factory: Callable[[str], str] | None = None) -> None:
        self._identifier_factory = identifier_factory or _new_identifier

    def initialize(self, report: Mapping[str, Any]) -> dict[str, Any]:
        """创建稳定案件 ID，仅对新解析器草稿使用自然顺序。"""
        value = copy.deepcopy(dict(report))
        introduction = _introduction(value)
        evidence = self._evidence_items(introduction.get("evidence_list"), ())
        introduction["evidence_list"] = _natural_order(evidence)
        snapshots = self._inspector_snapshots(introduction, ())
        if snapshots or isinstance(introduction.get("inspector_snapshots"), list):
            introduction["inspector_snapshots"] = snapshots
        return value

    def prepare_save(
        self, previous_report: Mapping[str, Any] | None, report: Mapping[str, Any],
    ) -> dict[str, Any]:
        """保留提交数组顺序，同时从草稿恢复缺失的稳定 ID。"""
        value = copy.deepcopy(dict(report))
        introduction = _introduction(value)
        previous_intro = _introduction(copy.deepcopy(dict(previous_report or {})))
        introduction["evidence_list"] = self._evidence_items(
            introduction.get("evidence_list"), previous_intro.get("evidence_list", ()),
        )
        snapshots = self._inspector_snapshots(
            introduction, previous_intro.get("inspector_snapshots", ()),
        )
        if snapshots or isinstance(introduction.get("inspector_snapshots"), list):
            introduction["inspector_snapshots"] = snapshots
        return value

    def _evidence_items(self, raw: Any, previous: Any) -> list[dict[str, Any]]:
        available = _available_identifiers(previous, "evidence_id", _evidence_match_key)
        items: list[dict[str, Any]] = []
        for index, item in enumerate(raw if isinstance(raw, list) else ()):
            if not isinstance(item, Mapping):
                continue
            normalized = dict(item)
            identifier = _identifier(normalized.get("evidence_id"))
            if identifier is None:
                identifier = _take_available(available, _evidence_match_key(normalized))
            normalized["evidence_id"] = identifier or self._identifier_factory("evidence")
            items.append(normalized)
        return items

    def _inspector_snapshots(
        self, introduction: dict[str, Any], previous: Any,
    ) -> list[dict[str, Any]]:
        raw = introduction.get("inspector_snapshots")
        if not isinstance(raw, list):
            raw = introduction.get("inspectors", ())
        available = _available_identifiers(previous, "snapshot_id", _inspector_match_key)
        snapshots: list[dict[str, Any]] = []
        for index, item in enumerate(raw if isinstance(raw, list) else ()):
            if not isinstance(item, Mapping):
                continue
            identifier = _identifier(item.get("snapshot_id"))
            if identifier is None:
                identifier = _take_available(available, _inspector_match_key(item))
            snapshots.append(project_case_inspector_snapshot(
                item, snapshot_id=identifier or self._identifier_factory("inspector"),
                selected_order=index,
            ))
        return snapshots


def _natural_order(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = [_number_key(item.get("evidence_number", "")) for item in items]
    if any(key is None for key in keys) or len(set(keys)) != len(keys):
        return items
    return [item for _, item in sorted(zip(keys, items), key=lambda pair: pair[0])]


def _number_key(value: object) -> tuple[int, ...] | None:
    parts = re.findall(r"\d+", str(value or ""))
    if not parts:
        return None
    result = tuple(int(part) for part in parts)
    return result if all(part <= _MAX_SAFE_INTEGER for part in result) else None


def _introduction(report: dict[str, Any]) -> dict[str, Any]:
    value = report.get("introduction")
    if not isinstance(value, dict):
        value = dict(value) if isinstance(value, Mapping) else {}
        report["introduction"] = value
    return value


def _available_identifiers(raw: Any, field: str, key: Callable[[Mapping[str, Any]], str]) -> dict[str, list[str]]:
    available: dict[str, list[str]] = {}
    for item in raw if isinstance(raw, list) else ():
        if isinstance(item, Mapping) and (identifier := _identifier(item.get(field))):
            available.setdefault(key(item), []).append(identifier)
    return available


def _take_available(available: dict[str, list[str]], key: str) -> str | None:
    values = available.get(key, [])
    return values.pop(0) if values else None


def _identifier(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _evidence_match_key(value: Mapping[str, Any]) -> str:
    return str(value.get("id") or value.get("evidence_number") or "")


def _inspector_match_key(value: Mapping[str, Any]) -> str:
    return "|".join(str(value.get(key, "")) for key in (
        "inspector_id", "id", "name", "unit", "position", "police_number", "badge_number",
    ))


def _new_identifier(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(12)}"
