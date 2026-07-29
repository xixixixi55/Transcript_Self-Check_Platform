"""Ordered, review-safe Legacy DTO view for every document consumer."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import Any

_REVIEW_ONLY_FIELDS = {
    "field_state", "field_states", "provenance", "review_color", "review_source",
    "review_state", "source", "source_color", "source_label", "confirmation",
    "pending_confirmation", "pending_review", "source_version",
}


def project_ordered_legacy_report(report: Mapping[str, Any]) -> dict[str, Any]:
    """Make the saved CaseDraft array order the only Legacy document order.

    This intentionally never applies a natural-number sort.  The CaseDraft has
    already stored either the one-time parser default or the user's drag order.
    """
    result = copy.deepcopy(dict(report))
    result.pop("field_states", None)
    result.pop("review_metadata", None)
    introduction = _mapping(result, "introduction")
    evidence = _copy_items(introduction.get("evidence_list"))
    if evidence is not None:
        introduction["evidence_list"] = evidence
        _remove_review_metadata(evidence)
    _project_inspectors(introduction)
    _project_photo_groups(result, evidence or [])
    return result


def _project_inspectors(introduction: dict[str, Any]) -> None:
    snapshots = introduction.get("inspector_snapshots")
    if not isinstance(snapshots, list):
        return
    copied = _copy_items(snapshots)
    if copied is None:
        return
    _remove_review_metadata(copied)
    introduction["inspector_snapshots"] = copied
    introduction["inspectors"] = [
        {
            "name": _text(item.get("name")), "unit": _text(item.get("unit")),
            "badge_number": _text(item.get("police_number")),
        }
        for item in copied if isinstance(item, Mapping)
    ]


def _project_photo_groups(report: dict[str, Any], evidence: list[Any]) -> None:
    attachments = _mapping(report, "attachments")
    groups = _copy_items(attachments.get("photo_groups"))
    if groups is None or not all(isinstance(item, Mapping) for item in groups):
        return
    original_image_ids = _group_image_ids([dict(item) for item in groups])
    saved_photo_ids = _photo_ids(attachments.get("photo_ids"))
    ranks = _evidence_ranks(evidence)
    ordered = [
        dict(item) for _, item in sorted(
            enumerate(groups),
            key=lambda pair: (ranks.get(_text(pair[1].get("material_id")), len(ranks) + pair[0]), pair[0]),
        )
    ]
    for index, group in enumerate(ordered, 1):
        group["source_order"] = index
    attachments["photo_groups"] = ordered
    image_ids = _group_image_ids(ordered)
    if image_ids is not None and original_image_ids == saved_photo_ids:
        attachments["photo_ids"] = image_ids


def _evidence_ranks(evidence: list[Any]) -> dict[str, int]:
    ranks: dict[str, int] = {}
    for index, item in enumerate(evidence):
        if not isinstance(item, Mapping):
            continue
        for key in ("evidence_id", "id"):
            value = _text(item.get(key))
            if value and value not in ranks:
                ranks[value] = index
    return ranks


def _group_image_ids(groups: list[dict[str, Any]]) -> list[str] | None:
    values: list[str] = []
    for group in groups:
        images = group.get("ordered_image_ids")
        if not isinstance(images, list) or len(images) != 2:
            return None
        normalized = [_text(item) for item in images]
        if not all(normalized):
            return None
        values.extend(normalized)
    return values


def _photo_ids(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    values = [_text(item) for item in value]
    return values if all(values) else None


def _copy_items(value: Any) -> list[Any] | None:
    return [dict(item) if isinstance(item, Mapping) else item for item in value] if isinstance(value, list) else None


def _remove_review_metadata(items: list[Any]) -> None:
    for item in items:
        if isinstance(item, dict):
            for key in _REVIEW_ONLY_FIELDS:
                item.pop(key, None)


def _mapping(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        value = dict(value) if isinstance(value, Mapping) else {}
        parent[key] = value
    return value


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else "" if value is None else str(value).strip()
