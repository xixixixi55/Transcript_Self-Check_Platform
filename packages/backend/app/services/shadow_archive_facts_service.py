"""Build redacted archive facts without executing or rescanning the archive."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from .attachment2_plan_service import build_attachment2_pages, material_photo_groups
from .attachment_plan_service import MAX_PART_ROWS_PER_PAGE
from .shadow_fact_service import (
    archive_filename_fingerprints, expected_archive_filenames, fingerprint,
    fingerprint_values,
)


def with_archive_facts(
    snapshot: Any, manifest: Mapping[str, Any], context: Any, plan: Any,
    *, expected: bool, expected_plan: Any = None, expected_report: Mapping[str, Any] | None = None,
):
    if expected:
        return _expected_archive_facts(snapshot, expected_plan, expected_report)
    return _actual_archive_facts(snapshot, manifest, plan)


def _actual_archive_facts(snapshot: Any, manifest: Mapping[str, Any], plan: Any):
    parts = manifest.get("parts") if isinstance(manifest, Mapping) else None
    actual_parts = parts if isinstance(parts, list) else []
    return replace(
        snapshot,
        archive_manifest_present=True,
        archive_base_name=fingerprint(manifest.get("archive_base_name")),
        archive_part_filenames=archive_filename_fingerprints(
            [item.get("filename") for item in actual_parts if isinstance(item, Mapping)]
        ),
        # The published Manifest intentionally has no extracted-tree listing.
        archive_root_preserved=None,
        archive_relative_paths=None,
        archive_input_file_count=int_or_none(manifest.get("input_file_count")),
        archive_input_total_bytes=int_or_none(manifest.get("total_input_bytes")),
        archive_actual_bytes=int_or_none(manifest.get("actual_archive_bytes")),
        archive_part_count=len(actual_parts),
        archive_volume_tier_gb=int_or_none(manifest.get("volume_tier_gb")),
        archive_disc_numbers=fingerprint_values(_manifest_values(actual_parts, "disc_number")),
        archive_disc_dates=fingerprint_values(_manifest_values(actual_parts, "disc_date")),
        **_page_counts(plan),
    )


def _expected_archive_facts(
    snapshot: Any, archive_plan: Any, expected_report: Mapping[str, Any] | None,
):
    planned_facts = _planned_input_facts(archive_plan)
    if archive_plan is None or planned_facts is None or archive_plan.status != "planned":
        return replace(snapshot, archive_manifest_present=True, **_expected_page_counts(None, expected_report))
    relative_paths, file_count, total_bytes = planned_facts
    names = expected_archive_filenames(archive_plan.archive_base_name, archive_plan.expected_part_count)
    dates = [_disc_date(value) for value in archive_plan.expected_disc_numbers]
    return replace(
        snapshot,
        archive_manifest_present=True,
        archive_base_name=fingerprint(archive_plan.archive_base_name),
        archive_part_filenames=archive_filename_fingerprints(names),
        archive_root_preserved=None,
        archive_relative_paths=relative_paths,
        archive_input_file_count=file_count,
        archive_input_total_bytes=total_bytes,
        # Compression output size is not knowable from an ArchivePlan.
        archive_actual_bytes=None,
        archive_part_count=archive_plan.expected_part_count,
        archive_volume_tier_gb=archive_plan.volume_tier_gb,
        archive_disc_numbers=fingerprint_values(archive_plan.expected_disc_numbers),
        archive_disc_dates=fingerprint_values(dates),
        **_expected_page_counts(archive_plan.expected_part_count, expected_report),
    )


def _expected_page_counts(
    expected_part_count: int | None, report: Mapping[str, Any] | None,
) -> dict[str, int | None]:
    if not isinstance(expected_part_count, int) or expected_part_count < 1:
        return {"attachment1_page_count": None, "attachment2_page_count": None, "attachment3_page_count": None}
    attachment1_pages = (expected_part_count + MAX_PART_ROWS_PER_PAGE - 1) // MAX_PART_ROWS_PER_PAGE
    if expected_part_count % MAX_PART_ROWS_PER_PAGE == 0:
        attachment1_pages += 1
    attachment2_pages = None
    if isinstance(report, Mapping):
        attachment2_pages = len(build_attachment2_pages(material_photo_groups(report)))
    return {
        "attachment1_page_count": attachment1_pages,
        "attachment2_page_count": attachment2_pages,
        "attachment3_page_count": expected_part_count,
    }


def _planned_input_facts(plan: Any) -> tuple[str, int, int] | None:
    entries = getattr(plan, "source_entries", None)
    total = getattr(plan, "total_input_bytes", None)
    if not isinstance(entries, tuple) or not isinstance(total, int):
        return None
    if any(not isinstance(item.relative_path, str) or not isinstance(item.size_bytes, int) for item in entries):
        return None
    return (
        fingerprint_values(sorted(item.relative_path for item in entries)) or fingerprint("[]"),
        len(entries),
        total,
    )


def _manifest_values(parts: list[Any], key: str) -> list[Any]:
    return [item.get(key) for item in parts if isinstance(item, Mapping)]


def _disc_date(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value[2:6] + "-" + value[6:8] + "-" + value[8:10] if len(value) >= 10 and value.startswith("GP") else None


def _page_counts(plan: Any) -> dict[str, int | None]:
    return {
        "attachment1_page_count": len(plan.attachment1_pages) if plan is not None else None,
        "attachment2_page_count": len(plan.attachment2_pages) if plan is not None else None,
        "attachment3_page_count": len(plan.attachment3_pages) if plan is not None else None,
    }


def validated_manifest(manifest: Mapping[str, Any]) -> bool:
    return (
        isinstance(manifest, Mapping)
        and manifest.get("validation_status") == "validated"
        and isinstance(manifest.get("parts"), list)
    )


def int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


__all__ = ["int_or_none", "validated_manifest", "with_archive_facts"]
