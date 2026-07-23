"""Redacted, normalized comparisons for the Shadow migration mode."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ShadowMaterialFacts:
    kind: str | None
    evidence_number: str | None
    name: str | None
    model: str | None
    identifiers: tuple[tuple[str, str | None], ...]


@dataclass(frozen=True)
class ShadowComparableSnapshot:
    case_number: str | None
    materials: tuple[ShadowMaterialFacts, ...] | None
    inspection_time: str | None
    primary_software_status: str | None
    primary_software_name: str | None
    primary_software_version: str | None
    disc_sequence: str | None
    inspector_order: tuple[str, ...] | None
    archive_manifest_present: bool | None = None
    archive_base_name: str | None = None
    archive_part_filenames: tuple[str, ...] | None = None
    archive_root_preserved: bool | None = None
    archive_relative_paths: str | None = None
    archive_input_file_count: int | None = None
    archive_input_total_bytes: int | None = None
    archive_actual_bytes: int | None = None
    archive_part_count: int | None = None
    archive_volume_tier_gb: int | None = None
    archive_disc_numbers: str | None = None
    archive_disc_dates: str | None = None
    attachment1_page_count: int | None = None
    attachment2_page_count: int | None = None
    attachment3_page_count: int | None = None


@dataclass(frozen=True)
class ShadowDifference:
    field_path: str
    status: str
    diagnostic_code: str
    source: str = "legacy_formal_vs_shadow_projection"


@dataclass(frozen=True)
class ShadowComparisonResult:
    matched: bool
    differences: tuple[ShadowDifference, ...]
    diagnostic_codes: tuple[str, ...]
    stage: str = "parse"

    @property
    def status(self) -> str:
        if any(item.status == "not_comparable" for item in self.differences):
            return "not_comparable"
        return "matched" if self.matched else "different"

    def to_public_dict(self) -> dict[str, object]:
        """Return diagnostics only; comparable source values never leave memory."""
        return {
            "stage": self.stage,
            "status": self.status,
            "matched": self.matched,
            "differences": [
                {
                    "field_path": item.field_path,
                    "status": item.status,
                    "diagnostic_code": item.diagnostic_code,
                    "source": item.source,
                }
                for item in self.differences
            ],
            "diagnostic_codes": list(self.diagnostic_codes),
        }


def _compare_field(
    field_path: str, left: Any, right: Any, mismatch_code: str,
) -> ShadowDifference | None:
    if left is None and right is None:
        return ShadowDifference(
            field_path, "not_comparable", mismatch_code.replace("_MISMATCH", "_NOT_COMPARABLE"),
        )
    if left is None or right is None or left != right:
        return ShadowDifference(field_path, "mismatch", mismatch_code)
    return None


def _base_comparisons(
    legacy: ShadowComparableSnapshot, shadow: ShadowComparableSnapshot,
) -> tuple[tuple[str, Any, Any, str], ...]:
    legacy_materials = legacy.materials
    shadow_materials = shadow.materials
    return (
        ("case_number", legacy.case_number, shadow.case_number, "CASE_NUMBER_MISMATCH"),
        ("materials.count", _count(legacy_materials), _count(shadow_materials), "MATERIAL_COUNT_MISMATCH"),
        ("materials.kind", _kinds(legacy_materials), _kinds(shadow_materials), "MATERIAL_KIND_MISMATCH"),
        ("materials.evidence_number", _evidence_numbers(legacy_materials), _evidence_numbers(shadow_materials), "MATERIAL_NUMBER_MISMATCH"),
        ("materials.name", _material_names(legacy_materials), _material_names(shadow_materials), "MATERIAL_NAME_MISMATCH"),
        ("materials.model", _material_models(legacy_materials), _material_models(shadow_materials), "MATERIAL_MODEL_MISMATCH"),
        ("materials.identifiers", _identifiers(legacy_materials), _identifiers(shadow_materials), "IDENTIFIER_VALUE_MISMATCH"),
        ("inspection_time", legacy.inspection_time, shadow.inspection_time, "INSPECTION_TIME_MISMATCH"),
        ("software.primary.confirmation_status", legacy.primary_software_status, shadow.primary_software_status, "PRIMARY_SOFTWARE_STATUS_MISMATCH"),
        ("software.primary.name", legacy.primary_software_name, shadow.primary_software_name, "PRIMARY_SOFTWARE_NAME_MISMATCH"),
        ("software.primary.version", legacy.primary_software_version, shadow.primary_software_version, "PRIMARY_SOFTWARE_VERSION_MISMATCH"),
        ("attachments.disc_sequence", legacy.disc_sequence, shadow.disc_sequence, "DISC_SEQUENCE_MISMATCH"),
        ("inspectors.order", legacy.inspector_order, shadow.inspector_order, "INSPECTOR_ORDER_MISMATCH"),
    )


def _archive_comparisons(
    legacy: ShadowComparableSnapshot, shadow: ShadowComparableSnapshot, *, full: bool,
) -> tuple[tuple[str, Any, Any, str], ...]:
    rows = [
        ("archive.manifest_present", legacy.archive_manifest_present, shadow.archive_manifest_present, "ARCHIVE_MANIFEST_PRESENCE_MISMATCH"),
        ("archive.base_name", legacy.archive_base_name, shadow.archive_base_name, "ARCHIVE_BASE_NAME_MISMATCH"),
        ("archive.part_filenames", legacy.archive_part_filenames, shadow.archive_part_filenames, "ARCHIVE_RAR_NAME_MISMATCH"),
        ("archive.part_count", legacy.archive_part_count, shadow.archive_part_count, "ARCHIVE_PART_COUNT_MISMATCH"),
        ("archive.volume_tier_gb", legacy.archive_volume_tier_gb, shadow.archive_volume_tier_gb, "ARCHIVE_VOLUME_TIER_MISMATCH"),
        ("archive.disc_numbers", legacy.archive_disc_numbers, shadow.archive_disc_numbers, "ARCHIVE_DISC_NUMBER_MISMATCH"),
        ("archive.disc_dates", legacy.archive_disc_dates, shadow.archive_disc_dates, "ARCHIVE_DISC_DATE_MISMATCH"),
    ]
    if full:
        rows.extend([
            ("archive.root_preserved", legacy.archive_root_preserved, shadow.archive_root_preserved, "ARCHIVE_ROOT_PRESERVATION_MISMATCH"),
            ("archive.relative_paths", legacy.archive_relative_paths, shadow.archive_relative_paths, "ARCHIVE_RELATIVE_PATH_SET_MISMATCH"),
            ("archive.input_file_count", legacy.archive_input_file_count, shadow.archive_input_file_count, "ARCHIVE_INPUT_FILE_COUNT_MISMATCH"),
            ("archive.input_total_bytes", legacy.archive_input_total_bytes, shadow.archive_input_total_bytes, "ARCHIVE_INPUT_TOTAL_BYTES_MISMATCH"),
        ])
    return tuple(rows)


def compare_shadow_snapshots(
    legacy: ShadowComparableSnapshot, shadow: ShadowComparableSnapshot, *, stage: str = "parse",
) -> ShadowComparisonResult:
    rows = list(_base_comparisons(legacy, shadow))
    if stage in {"archive", "export"}:
        rows.extend(_archive_comparisons(legacy, shadow, full=stage == "archive"))
    if stage in {"archive", "export"}:
        rows.extend([
            ("attachments.attachment1.page_count", legacy.attachment1_page_count, shadow.attachment1_page_count, "ATTACHMENT1_PAGE_COUNT_MISMATCH"),
            ("attachments.attachment2.page_count", legacy.attachment2_page_count, shadow.attachment2_page_count, "ATTACHMENT2_PAGE_COUNT_MISMATCH"),
            ("attachments.attachment3.page_count", legacy.attachment3_page_count, shadow.attachment3_page_count, "ATTACHMENT3_PAGE_COUNT_MISMATCH"),
        ])
    differences = tuple(
        difference
        for field_path, left, right, code in rows
        for difference in (_compare_field(field_path, left, right, code),)
        if difference is not None
    )
    return ShadowComparisonResult(
        matched=not differences,
        differences=differences,
        diagnostic_codes=tuple(item.diagnostic_code for item in differences),
        stage=stage,
    )


def snapshot_from_legacy_report(report: Any) -> ShadowComparableSnapshot:
    from .shadow_fact_service import snapshot_from_legacy_report as build_snapshot

    return build_snapshot(report)


def snapshot_from_canonical(case: Any) -> ShadowComparableSnapshot:
    from .shadow_fact_service import snapshot_from_canonical as build_snapshot

    return build_snapshot(case)


def _count(materials: tuple[ShadowMaterialFacts, ...] | None) -> int | None:
    return None if materials is None else len(materials)


def _kinds(materials: tuple[ShadowMaterialFacts, ...] | None) -> tuple[str | None, ...] | None:
    return None if materials is None else tuple(item.kind for item in materials)


def _evidence_numbers(materials: tuple[ShadowMaterialFacts, ...] | None) -> tuple[str | None, ...] | None:
    return None if materials is None else tuple(item.evidence_number for item in materials)


def _material_names(materials: tuple[ShadowMaterialFacts, ...] | None) -> tuple[str | None, ...] | None:
    return None if materials is None else tuple(item.name for item in materials)


def _material_models(materials: tuple[ShadowMaterialFacts, ...] | None) -> tuple[str | None, ...] | None:
    return None if materials is None else tuple(item.model for item in materials)


def _identifiers(materials: tuple[ShadowMaterialFacts, ...] | None) -> tuple[tuple[tuple[str, str | None], ...], ...] | None:
    return None if materials is None else tuple(item.identifiers for item in materials)


__all__ = [
    "ShadowComparableSnapshot", "ShadowComparisonResult", "ShadowDifference",
    "ShadowMaterialFacts", "compare_shadow_snapshots", "snapshot_from_canonical",
    "snapshot_from_legacy_report",
]
