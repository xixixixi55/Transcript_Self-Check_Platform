"""Canonical attachment migration helpers."""

from __future__ import annotations

from typing import Any, Mapping

from .canonical_models_service import DiscSequence, ExtractListTable, MaterialPhotoGroup
from .disc_sequence_service import parse_disc_sequence


def migrate_legacy_attachments(report: Mapping[str, Any]) -> dict[str, Any]:
    """Project legacy attachment fields into the validated disc structure."""
    raw = report.get("attachments") or {}
    if not isinstance(raw, Mapping):
        raw = {}
    disc_number = "" if raw.get("disc_number") is None else str(raw.get("disc_number")).strip()
    parsed = parse_disc_sequence(disc_number)
    raw_extract = raw.get("extract_list") or {}
    extract_list = ExtractListTable(
        columns=[
            {"key": str(col.get("key", "")), "title": str(col.get("title", "")), "width": col.get("width")}
            for col in (raw_extract.get("columns") or [])
            if isinstance(col, Mapping)
        ],
        rows=[
            {str(k): str(v) for k, v in row.items()}
            for row in (raw_extract.get("rows") or [])
            if isinstance(row, Mapping)
        ],
    )
    raw_groups = raw.get("photo_groups")
    photo_groups = None
    if isinstance(raw_groups, list):
        parsed_groups: list[MaterialPhotoGroup] = []
        for item in raw_groups:
            if not isinstance(item, Mapping):
                continue
            ids = item.get("ordered_image_ids")
            if isinstance(ids, list) and len(ids) == 2 and all(isinstance(v, str) for v in ids):
                parsed_groups.append(MaterialPhotoGroup(
                    material_id=str(item.get("material_id", "")),
                    material_number=str(item.get("material_number", "")),
                    display_text=str(item.get("display_text", "")),
                    ordered_image_ids=(str(ids[0]), str(ids[1])),
                    source_order=int(item.get("source_order", 0)),
                ))
        photo_groups = parsed_groups if parsed_groups else None
    payload: dict[str, Any] = {
        "extract_list": extract_list,
        "photo_ids": list(raw.get("photo_ids") or []),
        "photo_groups": photo_groups,
        "disc_number": disc_number,
        "burning_date": None,
    }
    if parsed.valid and parsed.sequence is not None:
        sequence = parsed.sequence
        payload["burning_date"] = _format_disc_date(sequence.date)
        payload["disc_sequence"] = DiscSequence(
            prefix=sequence.prefix,
            date=sequence.date,
            start_number=sequence.start_number,
            number_width=sequence.number_width,
            first_disc_number=sequence.first_disc_number,
        )
    return payload


def _format_disc_date(value: str) -> str:
    year, month, day = value.split("-")
    return f"{year}年{int(month)}月{int(day)}日"
