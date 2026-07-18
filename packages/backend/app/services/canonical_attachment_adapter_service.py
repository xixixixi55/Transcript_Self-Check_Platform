"""Canonical attachment migration helpers."""

from __future__ import annotations

from typing import Any, Mapping

from .canonical_models_service import DiscSequence
from .disc_sequence_service import parse_disc_sequence


def migrate_legacy_attachments(report: Mapping[str, Any]) -> dict[str, Any]:
    """Project legacy attachment fields into the validated disc structure."""
    raw = report.get("attachments") or {}
    if not isinstance(raw, Mapping):
        raw = {}
    disc_number = "" if raw.get("disc_number") is None else str(raw.get("disc_number")).strip()
    parsed = parse_disc_sequence(disc_number)
    payload: dict[str, Any] = {
        "extract_list": raw.get("extract_list") or {},
        "photo_ids": list(raw.get("photo_ids") or []),
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
