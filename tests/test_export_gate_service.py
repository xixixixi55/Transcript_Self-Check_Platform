import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.export.export_gate_service import (  # noqa: E402
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


def test_attachment2_odd_count_uses_stable_code_and_user_message():
    result = evaluate_export_gate(ExportGateInput(photo_count_valid=False))
    assert not result.allowed
    assert result.blockers[0].code == ExportGateCode.ATTACHMENT2_IMAGE_COUNT_ODD
    assert result.blockers[0].code == ExportGateCode.ODD_PHOTO_COUNT
    assert result.blockers[0].message == "附件图片数量必须为偶数，请补充或删除一张图片后重新导出。"


def test_attachment2_invalid_image_and_plan_are_gate_blockers():
    result = evaluate_export_gate(ExportGateInput(
        photo_assets_valid=False,
        attachment_plan_valid=False,
    ))
    assert [item.code for item in result.blockers] == [
        ExportGateCode.ATTACHMENT2_IMAGE_INVALID,
        ExportGateCode.ATTACHMENT_PLAN_INVALID,
    ]


def test_attachment2_material_mapping_has_stable_blocker_code():
    result = evaluate_export_gate(ExportGateInput(
        photo_mapping_valid=False,
        photo_mapping_error_code="ATTACHMENT2_MATERIAL_IMAGE_COUNT_INVALID",
    ))
    assert not result.allowed
    assert result.blockers[0].code == "ATTACHMENT2_MATERIAL_IMAGE_COUNT_INVALID"
    assert "两张图片" in result.blockers[0].message
