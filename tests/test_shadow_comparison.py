"""规范化、脱敏 Shadow 比较事实的合成数据测试。"""

import json
import os
import sys
from dataclasses import replace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.canonical.canonical_adapter_service import inspection_report_to_canonical
from app.services.shadow.shadow_comparison_service import (
    compare_shadow_snapshots, snapshot_from_canonical, snapshot_from_legacy_report,
)


def _report():
    return {
        "case_number": " SYNTHETIC-CASE-001 ",
        "introduction": {
            "evidence_list": [{
                "id": "synthetic-material-1", "evidence_number": "E-001",
                "device_type": " 手机 ", "imei1": " 123-456 78901234 ",
            }],
            "inspection_time_range": "2026-07-22 09:00 ~ 10:00",
            "inspectors": [{"name": "Synthetic inspector", "unit": "Synthetic unit", "badge_number": "S-001"}],
        },
        "inspection": {
            "primary_software": {
                "name": "Synthetic Tool", "version": "V1.0",
                "confirmation_status": "confirmed_by_report",
            },
            "software_tools": [{"name": "Synthetic Tool", "version": "V1.0"}],
            "result": {},
        },
        "attachments": {"disc_number": "GP20260722-01"},
    }


def _snapshots():
    report = _report()
    canonical = inspection_report_to_canonical(report).canonical_case
    return snapshot_from_legacy_report(report), snapshot_from_canonical(canonical)


def test_shadow_compares_normalized_business_values_not_presence_only():
    legacy, canonical = _snapshots()

    result = compare_shadow_snapshots(legacy, canonical)

    assert result.matched
    assert result.differences == ()


def test_shadow_reports_real_case_number_difference_without_original_value():
    legacy, canonical = _snapshots()
    changed = replace(canonical, case_number="SYNTHETIC-OTHER")

    result = compare_shadow_snapshots(legacy, changed)
    serialized = json.dumps(result.to_public_dict(), ensure_ascii=False)

    assert not result.matched
    assert "CASE_NUMBER_MISMATCH" in result.diagnostic_codes
    assert "SYNTHETIC-CASE-001" not in serialized
    assert "SYNTHETIC-OTHER" not in serialized


def test_shadow_compares_identifier_value_and_software_name_version():
    legacy, canonical = _snapshots()
    changed_material = replace(
        canonical.materials[0],
        identifiers=(("imei1", "999999999999999"),),
    )
    changed = replace(
        canonical,
        materials=(changed_material,),
        primary_software_name="other",
        primary_software_version="2.0",
    )

    result = compare_shadow_snapshots(legacy, changed)

    assert "IDENTIFIER_VALUE_MISMATCH" in result.diagnostic_codes
    assert "PRIMARY_SOFTWARE_NAME_MISMATCH" in result.diagnostic_codes
    assert "PRIMARY_SOFTWARE_VERSION_MISMATCH" in result.diagnostic_codes


def test_shadow_compares_time_and_disc_semantics():
    legacy, canonical = _snapshots()
    changed = replace(canonical, inspection_time="2026-07-23 09:00 ~ 10:00", disc_sequence=None)

    result = compare_shadow_snapshots(legacy, changed)

    assert "INSPECTION_TIME_MISMATCH" in result.diagnostic_codes
    assert "DISC_SEQUENCE_MISMATCH" in result.diagnostic_codes


def test_missing_values_are_not_silently_treated_as_matched():
    legacy, canonical = _snapshots()
    missing = replace(canonical, primary_software_name=None, primary_software_version=None)

    result = compare_shadow_snapshots(legacy, missing)

    assert not result.matched
    assert "PRIMARY_SOFTWARE_NAME_MISMATCH" in result.diagnostic_codes
    both_missing = replace(legacy, disc_sequence=None)
    both_missing_result = compare_shadow_snapshots(both_missing, replace(missing, disc_sequence=None))
    assert both_missing_result.status == "not_comparable"
    assert "DISC_SEQUENCE_NOT_COMPARABLE" in both_missing_result.diagnostic_codes


def test_archive_contract_missing_root_listing_is_explicitly_not_comparable():
    legacy, canonical = _snapshots()
    legacy = replace(legacy, archive_root_preserved=None)
    canonical = replace(canonical, archive_root_preserved=None)

    result = compare_shadow_snapshots(legacy, canonical, stage="archive")

    assert result.status == "not_comparable"
    assert "ARCHIVE_ROOT_PRESERVATION_NOT_COMPARABLE" in result.diagnostic_codes


def test_archive_contract_compares_names_paths_counts_and_bytes_without_values():
    legacy, shadow = _snapshots()
    common = {
        "archive_manifest_present": True,
        "archive_part_count": 1,
        "archive_volume_tier_gb": 4,
        "archive_actual_bytes": 300,
        "archive_disc_numbers": "disc-hash",
        "archive_disc_dates": "date-hash",
        "attachment1_page_count": 1,
        "attachment2_page_count": 0,
        "attachment3_page_count": 1,
    }
    legacy = replace(
        legacy, **common,
        archive_base_name="legacy-base-hash",
        archive_part_filenames=("legacy-part-hash",),
        archive_root_preserved=True,
        archive_relative_paths="legacy-path-set-hash",
        archive_input_file_count=1,
        archive_input_total_bytes=100,
    )
    shadow = replace(
        shadow, **common,
        archive_base_name="shadow-base-hash",
        archive_part_filenames=("shadow-part-hash",),
        archive_root_preserved=False,
        archive_relative_paths="shadow-path-set-hash",
        archive_input_file_count=2,
        archive_input_total_bytes=200,
    )

    result = compare_shadow_snapshots(legacy, shadow, stage="archive")
    serialized = json.dumps(result.to_public_dict(), ensure_ascii=False)

    for code in (
        "ARCHIVE_BASE_NAME_MISMATCH",
        "ARCHIVE_RAR_NAME_MISMATCH",
        "ARCHIVE_ROOT_PRESERVATION_MISMATCH",
        "ARCHIVE_RELATIVE_PATH_SET_MISMATCH",
        "ARCHIVE_INPUT_FILE_COUNT_MISMATCH",
        "ARCHIVE_INPUT_TOTAL_BYTES_MISMATCH",
    ):
        assert code in result.diagnostic_codes
    assert "legacy-base-hash" not in serialized
    assert "shadow-path-set-hash" not in serialized


def test_serialization_contains_only_codes_and_no_sensitive_values():
    legacy, canonical = _snapshots()
    result = compare_shadow_snapshots(
        legacy, replace(canonical, case_number=None), stage="parse",
    )
    serialized = json.dumps(result.to_public_dict(), ensure_ascii=False)

    assert "SYNTHETIC-CASE-001" not in serialized
    assert "123-456" not in serialized
    assert "Synthetic inspector" not in serialized
    assert "CASE_NUMBER_MISMATCH" in serialized
