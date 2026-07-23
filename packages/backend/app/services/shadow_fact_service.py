"""Normalized, non-public facts used by Shadow comparisons."""

from __future__ import annotations

import hashlib
import unicodedata
from collections.abc import Mapping
from typing import Any

from .canonical_models_service import CanonicalInspectionCase
from .disc_sequence_service import parse_disc_sequence
from .shadow_comparison_service import ShadowComparableSnapshot, ShadowMaterialFacts


def normalize_business_text(value: Any) -> str:
    if value is None or isinstance(value, (dict, list, tuple, set, bool)):
        return ""
    return " ".join(unicodedata.normalize("NFKC", str(value)).split()).casefold()


def fingerprint(value: Any, *, identifier: bool = False) -> str | None:
    normalized = normalize_business_text(value)
    if identifier:
        normalized = normalized.replace(" ", "").replace("-", "")
    if not normalized:
        return None
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def fingerprint_values(values: Any, *, identifier: bool = False) -> str | None:
    if values is None:
        return None
    normalized = tuple(
        normalize_business_text(item) for item in values
    )
    if identifier:
        normalized = tuple(item.replace(" ", "").replace("-", "") for item in normalized)
    if not normalized:
        return fingerprint("[]")
    return fingerprint("|".join(f"{len(item)}:{item}" for item in normalized))


def expected_archive_filenames(base_name: str | None, part_count: int | None) -> tuple[str, ...] | None:
    if not base_name or not isinstance(part_count, int) or part_count < 1:
        return None
    if part_count == 1:
        return (f"{base_name}.rar",)
    return tuple(f"{base_name}.part{index}.rar" for index in range(1, part_count + 1))


def archive_filename_fingerprints(filenames: Any) -> tuple[str, ...] | None:
    if filenames is None:
        return None
    return tuple(
        item for item in (fingerprint(value) for value in filenames) if item is not None
    )


def _legacy_kind(item: Mapping[str, Any]) -> str | None:
    """Read the kind already emitted by the formal Legacy DTO.

    This intentionally does not call the canonical material adapter. Shadow's
    Legacy facts must observe the result that Legacy would render, even when
    the canonical migration interprets the same input differently.
    """
    declared = normalize_business_text(item.get("material_type"))
    if declared in {"phone", "tablet", "unconfirmed"}:
        return declared
    device_type = normalize_business_text(item.get("device_type"))
    if device_type in {"phone", "smartphone", "iphone", "手机", "智能手机"}:
        return "phone"
    if device_type in {"tablet", "ipad", "平板", "平板电脑"}:
        return "tablet"
    return "unconfirmed" if device_type else None


def _material_facts(item: Mapping[str, Any]) -> ShadowMaterialFacts:
    return ShadowMaterialFacts(
        kind=_legacy_kind(item),
        evidence_number=fingerprint(item.get("evidence_number")),
        name=fingerprint(item.get("device_type")),
        model=fingerprint(item.get("model")),
        identifiers=tuple(
            (identifier_type, fingerprint(item.get(identifier_type), identifier=True))
            for identifier_type in ("imei1", "imei2", "serial_number")
            if fingerprint(item.get(identifier_type), identifier=True) is not None
        ),
    )


def _legacy_materials(introduction: Mapping[str, Any]) -> tuple[ShadowMaterialFacts, ...] | None:
    if "evidence_list" not in introduction:
        return None
    values = introduction.get("evidence_list")
    if not isinstance(values, list):
        return None
    return tuple(
        _material_facts(item) if isinstance(item, Mapping)
        else ShadowMaterialFacts(None, None, None, None, ())
        for item in values
    )


def _legacy_software(inspection: Mapping[str, Any]) -> tuple[str | None, str | None, str | None]:
    primary = inspection.get("primary_software")
    result = inspection.get("result") or {}
    if not isinstance(primary, Mapping):
        return None, fingerprint(result.get("software_name")), fingerprint(result.get("software_version"))
    status = normalize_business_text(primary.get("confirmation_status")) or None
    return status, fingerprint(primary.get("name")), fingerprint(primary.get("version"))


def _disc_fingerprint(value: Any) -> str | None:
    raw = normalize_business_text(value)
    if not raw:
        return None
    parsed = parse_disc_sequence(raw)
    if parsed.valid and parsed.sequence is not None:
        sequence = parsed.sequence
        return fingerprint("|".join((sequence.prefix, sequence.date, str(sequence.start_number), str(sequence.number_width))))
    return fingerprint(f"invalid|{raw}")


def _inspector_order(introduction: Mapping[str, Any]) -> tuple[str, ...] | None:
    key = "inspector_snapshots" if "inspector_snapshots" in introduction else "inspectors"
    values = introduction.get(key)
    if not isinstance(values, list):
        return None
    return tuple(
        fingerprint("|".join((
            normalize_business_text(item.get("name")),
            normalize_business_text(item.get("unit")),
            normalize_business_text(item.get("police_number", item.get("badge_number"))),
        ))) or ""
        for item in values if isinstance(item, Mapping)
    )


def snapshot_from_legacy_report(report: Mapping[str, Any]) -> ShadowComparableSnapshot:
    introduction = report.get("introduction") or {}
    inspection = report.get("inspection") or {}
    status, name, version = _legacy_software(inspection)
    return ShadowComparableSnapshot(
        case_number=fingerprint(report.get("case_number")),
        materials=_legacy_materials(introduction),
        inspection_time=fingerprint(introduction.get("inspection_time_range")),
        primary_software_status=status,
        primary_software_name=name,
        primary_software_version=version,
        disc_sequence=_disc_fingerprint((report.get("attachments") or {}).get("disc_number")),
        inspector_order=_inspector_order(introduction),
    )


def snapshot_from_canonical(case: CanonicalInspectionCase) -> ShadowComparableSnapshot:
    primary = case.primary_software
    if primary is None:
        primary = next((tool for tool in case.software_tools if tool.category == "main_forensic"), None)
    materials = tuple(
        ShadowMaterialFacts(
            kind=material.type,
            evidence_number=fingerprint(material.evidence_number),
            name=fingerprint(material.name),
            model=fingerprint(material.model),
            identifiers=tuple(
                (identifier.type, fingerprint(identifier.value, identifier=True))
                for identifier in material.identifiers
            ),
        )
        for material in case.materials
    )
    inspectors = tuple(
        fingerprint("|".join((
            normalize_business_text(item.name),
            normalize_business_text(item.unit),
            normalize_business_text(item.police_number),
        ))) or ""
        for item in sorted(case.inspectors, key=lambda value: value.selected_order or 0)
    )
    sequence = case.attachments.disc_sequence
    disc_value = (
        fingerprint("|".join((sequence.prefix, sequence.date, str(sequence.start_number), str(sequence.number_width))))
        if sequence is not None else None
    )
    return ShadowComparableSnapshot(
        case_number=fingerprint(case.case_info.case_number),
        materials=materials,
        inspection_time=fingerprint(case.inspection_period.time_range),
        primary_software_status=(normalize_business_text(primary.confirmation_status) if primary else None),
        primary_software_name=fingerprint(primary.name) if primary else None,
        primary_software_version=fingerprint(primary.version) if primary else None,
        disc_sequence=disc_value,
        inspector_order=inspectors,
    )


__all__ = [
    "archive_filename_fingerprints", "expected_archive_filenames", "fingerprint",
    "fingerprint_values", "normalize_business_text", "snapshot_from_canonical",
    "snapshot_from_legacy_report",
]
