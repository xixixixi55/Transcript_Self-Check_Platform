"""Synthetic tests for redacted shadow comparison facts."""

import json
import os
import sys
from dataclasses import asdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.canonical_adapter_service import inspection_report_to_canonical
from app.services.shadow_comparison_service import (
    compare_shadow_snapshots,
    snapshot_from_canonical,
    snapshot_from_legacy_report,
)


def _legacy_report():
    return {
        "case_number": "CASE-001",
        "introduction": {
            "evidence_list": [
                {"imei1": "imei-synthetic-1", "evidence_number": "E-001"}
            ],
            "inspection_time_range": "synthetic-range",
            "inspectors": [{"name": "Synthetic inspector"}],
        },
        "inspection": {
            "software_tools": [{"name": "Synthetic tool", "version": "1.0"}]
        },
    }


def test_shadow_comparison_matches_minimum_non_sensitive_facts():
    report = _legacy_report()
    canonical = inspection_report_to_canonical(report).canonical_case

    result = compare_shadow_snapshots(
        snapshot_from_legacy_report(report), snapshot_from_canonical(canonical)
    )

    assert result.matched
    assert result.differences == ()
    assert "Synthetic inspector" not in repr(snapshot_from_legacy_report(report))


def test_shadow_comparison_reports_codes_without_sensitive_values():
    report = _legacy_report()
    canonical = inspection_report_to_canonical(report).canonical_case
    canonical.case_info.case_number = ""

    result = compare_shadow_snapshots(
        snapshot_from_legacy_report(report), snapshot_from_canonical(canonical)
    )

    assert not result.matched
    assert result.differences[0].field_path == "case_number"
    assert result.differences[0].diagnostic_code == "CASE_NUMBER_PRESENCE_MISMATCH"
    rendered = repr(result)
    assert "CASE-001" not in rendered
    assert "imei-synthetic-1" not in rendered


def test_shadow_comparison_serialization_contains_only_safe_diagnostics():
    report = _legacy_report()
    canonical = inspection_report_to_canonical(report).canonical_case
    canonical.case_info.case_number = ""

    result = compare_shadow_snapshots(
        snapshot_from_legacy_report(report), snapshot_from_canonical(canonical)
    )
    serialized = json.dumps(asdict(result), ensure_ascii=False)

    assert "CASE-001" not in serialized
    assert "Synthetic inspector" not in serialized
    assert "imei-synthetic-1" not in serialized
    assert "case_number" in serialized
    assert "CASE_NUMBER_PRESENCE_MISMATCH" in serialized
