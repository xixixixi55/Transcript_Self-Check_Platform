import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.export_gate_service import (  # noqa: E402
    ExportGateCode,
    ExportGateInput,
    evaluate_export_gate,
)


def test_archive_gate_returns_stable_codes_for_execution_boundaries():
    result = evaluate_export_gate(
        ExportGateInput(
            automatic_archive_required=True,
            winrar_available=False,
            archive_blocker_code="ARCHIVE_INPUT_CHANGED",
        )
    )
    assert not result.allowed
    assert [item.code for item in result.blockers] == [
        ExportGateCode.WINRAR_UNAVAILABLE, "ARCHIVE_INPUT_CHANGED"
    ]


def test_manifest_missing_and_invalid_are_distinct_gate_results():
    missing = evaluate_export_gate(ExportGateInput(archive_manifest_required=True))
    assert [item.code for item in missing.blockers] == [ExportGateCode.ARCHIVE_MANIFEST_MISSING]
    invalid = evaluate_export_gate(ExportGateInput(archive_manifest_required=True, archive_manifest_present=True, archive_manifest_valid=False))
    assert [item.code for item in invalid.blockers] == [ExportGateCode.ARCHIVE_PARTS_INVALID]
