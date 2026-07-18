"""Safe, in-memory comparisons for the shadow migration mode."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping

from .canonical_models_service import CanonicalInspectionCase
from .disc_sequence_service import parse_disc_sequence


_COMPARABLE_PRIMARY_STATUSES = {
    "confirmed_by_report",
    "confirmed_by_user",
    "unconfirmed",
    "unavailable",
}
_NOT_COMPARABLE = "not_comparable"


@dataclass(frozen=True)
class ShadowComparableSnapshot:
    case_number_present: bool
    material_count: int
    material_kind_status: tuple[str, ...]
    identifier_types: tuple[tuple[str, ...], ...]
    inspection_time_present: bool
    primary_software_status: str
    primary_software_name_present: bool
    primary_software_version_present: bool
    first_disc_number_valid: bool
    disc_date_present: bool
    inspector_count: int
    inspector_order: tuple[str, ...]


@dataclass(frozen=True)
class ShadowDifference:
    field_path: str
    status: str
    diagnostic_code: str


@dataclass(frozen=True)
class ShadowComparisonResult:
    matched: bool
    differences: tuple[ShadowDifference, ...]
    diagnostic_codes: tuple[str, ...]


def _safe_order_token(name: str, unit: str, police_number: str) -> str:
    """Keep order comparison deterministic without retaining identifying text."""

    raw = "|".join((name, unit, police_number)).encode("utf-8")
    return sha256(raw).hexdigest()[:16]


def _identifier_types(material: Mapping[str, Any]) -> tuple[str, ...]:
    values = material.get("identifiers", [])
    return tuple(sorted(str(item.get("type", "")) for item in values))


def _normalize_primary_status(value: Any, unavailable: str) -> str:
    status = str(value or "").strip()
    return status if status in _COMPARABLE_PRIMARY_STATUSES else unavailable


def _legacy_primary_facts(
    inspection: Mapping[str, Any],
) -> tuple[str, bool, bool]:
    raw_primary = inspection.get("primary_software")
    result = inspection.get("result") or {}
    if isinstance(raw_primary, Mapping):
        return (
            _normalize_primary_status(raw_primary.get("confirmation_status"), _NOT_COMPARABLE),
            bool(str(raw_primary.get("name", "")).strip()),
            bool(str(raw_primary.get("version", "")).strip()),
        )
    return (
        _NOT_COMPARABLE,
        bool(str(result.get("software_name", "")).strip()),
        bool(str(result.get("software_version", "")).strip()),
    )


def _legacy_disc_facts(report: Mapping[str, Any]) -> tuple[bool, bool]:
    attachments = report.get("attachments") or {}
    disc_number = attachments.get("disc_number", "")
    parsed = parse_disc_sequence(disc_number)
    return parsed.valid, bool(parsed.valid and parsed.sequence and parsed.sequence.date)


def snapshot_from_legacy_report(report: Mapping[str, Any]) -> ShadowComparableSnapshot:
    introduction = report.get("introduction", {})
    inspection = report.get("inspection", {})
    materials = introduction.get("evidence_list", [])
    primary_status, primary_name_present, primary_version_present = _legacy_primary_facts(
        inspection
    )
    first_disc_number_valid, disc_date_present = _legacy_disc_facts(report)
    return ShadowComparableSnapshot(
        case_number_present=bool(str(report.get("case_number", "")).strip()),
        material_count=len(materials),
        material_kind_status=tuple("unconfirmed" for _ in materials),
        identifier_types=tuple(
            tuple(
                sorted(
                    identifier_type
                    for identifier_type in ("imei1", "imei2", "serial_number")
                    if str(material.get(identifier_type, "")).strip()
                )
            )
            for material in materials
        ),
        inspection_time_present=bool(
            str(introduction.get("inspection_time_range", "")).strip()
        ),
        primary_software_status=primary_status,
        primary_software_name_present=primary_name_present,
        primary_software_version_present=primary_version_present,
        first_disc_number_valid=first_disc_number_valid,
        disc_date_present=disc_date_present,
        inspector_count=len(introduction.get("inspectors", [])),
        inspector_order=tuple(
            _safe_order_token(
                str(item.get("name", "")),
                str(item.get("unit", "")),
                str(item.get("badge_number", "")),
            )
            for item in introduction.get("inspectors", [])
        ),
    )


def snapshot_from_canonical(
    case: CanonicalInspectionCase,
) -> ShadowComparableSnapshot:
    primary = case.primary_software
    if primary is None:
        primary_tools = [
            tool for tool in case.software_tools if tool.category == "main_forensic"
        ]
        primary = primary_tools[0] if primary_tools else None
    first_disc_number_valid = bool(case.attachments.disc_sequence)
    disc_date_present = bool(
        case.attachments.disc_sequence
        and case.attachments.disc_sequence.date.strip()
    )
    return ShadowComparableSnapshot(
        case_number_present=bool(case.case_info.case_number.strip()),
        material_count=len(case.materials),
        material_kind_status=tuple(material.type for material in case.materials),
        identifier_types=tuple(
            tuple(sorted(identifier.type for identifier in material.identifiers))
            for material in case.materials
        ),
        inspection_time_present=bool(case.inspection_period.time_range.strip()),
        primary_software_status=(
            _normalize_primary_status(primary.confirmation_status, "unavailable")
            if primary is not None
            else "unavailable"
        ),
        primary_software_name_present=bool(primary and primary.name.strip()),
        primary_software_version_present=bool(primary and primary.version.strip()),
        first_disc_number_valid=first_disc_number_valid,
        disc_date_present=disc_date_present,
        inspector_count=len(case.inspectors),
        inspector_order=tuple(
            _safe_order_token(
                inspector.name,
                inspector.unit,
                inspector.police_number,
            )
            for inspector in sorted(
                case.inspectors, key=lambda item: item.selected_order
            )
        ),
    )


def compare_shadow_snapshots(
    legacy: ShadowComparableSnapshot,
    canonical: ShadowComparableSnapshot,
) -> ShadowComparisonResult:
    comparisons = (
        ("case_number", legacy.case_number_present, canonical.case_number_present, "CASE_NUMBER_PRESENCE_MISMATCH"),
        ("materials", legacy.material_count, canonical.material_count, "MATERIAL_COUNT_MISMATCH"),
        ("materials.type", legacy.material_kind_status, canonical.material_kind_status, "MATERIAL_KIND_STATUS_MISMATCH"),
        ("materials.identifiers.type", legacy.identifier_types, canonical.identifier_types, "IDENTIFIER_TYPE_SET_MISMATCH"),
        ("inspection_time", legacy.inspection_time_present, canonical.inspection_time_present, "INSPECTION_TIME_PRESENCE_MISMATCH"),
        ("software.primary.confirmation_status", legacy.primary_software_status, canonical.primary_software_status, "PRIMARY_SOFTWARE_STATUS_MISMATCH"),
        ("software.primary.name_present", legacy.primary_software_name_present, canonical.primary_software_name_present, "PRIMARY_SOFTWARE_NAME_PRESENCE_MISMATCH"),
        ("software.primary.version_present", legacy.primary_software_version_present, canonical.primary_software_version_present, "PRIMARY_SOFTWARE_VERSION_PRESENCE_MISMATCH"),
        ("attachments.first_disc_number_valid", legacy.first_disc_number_valid, canonical.first_disc_number_valid, "FIRST_DISC_NUMBER_VALIDITY_MISMATCH"),
        ("attachments.disc_date_present", legacy.disc_date_present, canonical.disc_date_present, "DISC_DATE_PRESENCE_MISMATCH"),
        ("inspectors.count", legacy.inspector_count, canonical.inspector_count, "INSPECTOR_COUNT_MISMATCH"),
        ("inspectors.order", legacy.inspector_order, canonical.inspector_order, "INSPECTOR_ORDER_MISMATCH"),
    )
    differences = tuple(
        ShadowDifference(
            field_path=field_path,
            status="mismatch",
            diagnostic_code=diagnostic_code,
        )
        for field_path, legacy_value, canonical_value, diagnostic_code in comparisons
        if legacy_value != canonical_value
        and not (
            field_path == "software.primary.confirmation_status"
            and _NOT_COMPARABLE in {legacy_value, canonical_value}
        )
    )
    return ShadowComparisonResult(
        matched=not differences,
        differences=differences,
        diagnostic_codes=tuple(item.diagnostic_code for item in differences),
    )
