"""SYNTHETIC T010 coverage for the single saved-order Legacy projection."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.attachment_plan_service import build_attachment_plan  # noqa: E402
from app.services.archive_manifest_projection_service import project_manifest_to_legacy_report_with_plan  # noqa: E402
from app.services.document_builder_service import build_record_document  # noqa: E402
from app.services.legacy_report_projection_service import project_ordered_legacy_report  # noqa: E402


def _report():
    return {
        "title": "SYNTHETIC/TEST Record", "document_number": "SYNTHETIC-DOC",
        "field_states": {"evidence.SYNTHETIC-10.model": {"source": "user"}},
        "introduction": {
            "entrust_unit": "SYNTHETIC-UNIT", "entrust_persons": [], "entrust_time": "",
            "case_summary": "SYNTHETIC", "inspection_requirement": "", "inspection_time_range": "",
            "inspection_place": "SYNTHETIC-PLACE",
            "evidence_list": [
                {"id": "material-10", "evidence_id": "SYNTHETIC-EVIDENCE-10", "device_type": "SYNTHETIC-TEN", "evidence_number": "SYNTHETIC-10", "review_color": "SYNTHETIC-UI-COLOR"},
                {"id": "material-2", "evidence_id": "SYNTHETIC-EVIDENCE-2", "device_type": "SYNTHETIC-TWO", "evidence_number": "SYNTHETIC-2", "review_source": "SYNTHETIC-UI-SOURCE"},
            ],
            "inspectors": [{"name": "SYNTHETIC-LIBRARY-STALE", "unit": "SYNTHETIC", "badge_number": "000"}],
            "inspector_snapshots": [
                {"snapshot_id": "SYNTHETIC-SNAPSHOT-B", "name": "SYNTHETIC-B", "unit": "SYNTHETIC-UNIT", "police_number": "SYNTHETIC-002", "source_version": "SYNTHETIC-UI-SOURCE"},
                {"snapshot_id": "SYNTHETIC-SNAPSHOT-A", "name": "SYNTHETIC-A", "unit": "SYNTHETIC-UNIT", "police_number": "SYNTHETIC-001"},
            ],
        },
        "inspection": {
            "method": "SYNTHETIC-METHOD", "hardware_device": "SYNTHETIC-HARDWARE",
            "primary_software": {"name": "SYNTHETIC-TOOL", "version": "1.0", "confirmation_status": "confirmed_by_report"},
            "software_tools": [{"name": "WinRAR压缩管理软件", "version": "6.24"}, {"name": "Python hashlib", "version": "3.12"}],
            "process_steps": [], "result": {"evidence_number": "SYNTHETIC-2、SYNTHETIC-10", "software_name": "SYNTHETIC-TOOL", "software_version": "1.0", "data_summary": "SYNTHETIC", "rar_filename": "SYNTHETIC.rar", "md5_hash": "", "file_size": ""},
        },
        "attachments": {
            "photo_ids": ["photo-2a", "photo-2b", "photo-10a", "photo-10b"], "disc_number": "GP20260706-01",
            "extract_list": {"columns": [], "rows": []},
            "photo_groups": [
                {"material_id": "material-2", "material_number": "SYNTHETIC-2", "display_text": "检材SYNTHETIC-2照片", "ordered_image_ids": ["photo-2a", "photo-2b"], "source_order": 1},
                {"material_id": "material-10", "material_number": "SYNTHETIC-10", "display_text": "检材SYNTHETIC-10照片", "ordered_image_ids": ["photo-10a", "photo-10b"], "source_order": 2},
            ],
        },
    }


def _manifest():
    return {"manifest_id": "SYNTHETIC-MANIFEST", "validation_status": "validated", "volume_size_bytes": 4_000_000_000, "parts": [
        {"part_id": "SYNTHETIC-PART-1", "part_number": 1, "filename": "SYNTHETIC.part1.rar", "size_bytes": 100, "md5": "1" * 32, "disc_number": "GP20260706-01", "disc_date": "2026-07-06", "disc_capacity_bytes": 4_000_000_000},
    ]}


def test_saved_drag_order_drives_body_attachment_plan_and_person_snapshot_projection():
    projected = project_ordered_legacy_report(_report())
    plan = build_attachment_plan(_manifest(), projected)
    manifest_report, manifest_plan = project_manifest_to_legacy_report_with_plan(_report(), _manifest())
    commands = build_record_document(projected)
    paragraphs = "\n".join(
        item.get("props", {}).get("text", "") for item in commands if item.get("type") == "paragraph"
    )

    assert [item["evidence_number"] for item in projected["introduction"]["evidence_list"]] == ["SYNTHETIC-10", "SYNTHETIC-2"]
    assert [item["name"] for item in projected["introduction"]["inspectors"]] == ["SYNTHETIC-B", "SYNTHETIC-A"]
    assert [item["material_number"] for item in projected["attachments"]["photo_groups"]] == ["SYNTHETIC-10", "SYNTHETIC-2"]
    assert projected["attachments"]["photo_ids"] == ["photo-10a", "photo-10b", "photo-2a", "photo-2b"]
    assert plan.attachment1_pages[0].source_text == "SYNTHETIC-10、SYNTHETIC-2内提取"
    assert [page.inspection_result_material_numbers for page in plan.attachment2_pages] == [("SYNTHETIC-10", "SYNTHETIC-2")]
    assert manifest_plan == plan
    assert manifest_report["attachments"]["extract_list"]["rows"][0]["source"] == "SYNTHETIC-10、SYNTHETIC-2内提取"
    assert manifest_plan.attachment3_pages[0].filename == "SYNTHETIC.part1.rar"
    assert "经对编号为SYNTHETIC-10、SYNTHETIC-2号检材使用" in paragraphs
    assert paragraphs.index("SYNTHETIC-B") < paragraphs.index("SYNTHETIC-A")
    assert "SYNTHETIC-LIBRARY-STALE" not in paragraphs


def test_duplicate_or_unrecognizable_numbers_are_never_resorted_downstream():
    report = _report()
    report["introduction"]["evidence_list"] = [
        {"id": "SYNTHETIC-A", "evidence_number": "SYNTHETIC-10"},
        {"id": "SYNTHETIC-B", "evidence_number": "SYNTHETIC-2"},
        {"id": "SYNTHETIC-C", "evidence_number": "SYNTHETIC-2"},
        {"id": "SYNTHETIC-D", "evidence_number": "SYNTHETIC-UNKNOWN"},
    ]

    projected = project_ordered_legacy_report(report)

    assert [item["evidence_number"] for item in projected["introduction"]["evidence_list"]] == [
        "SYNTHETIC-10", "SYNTHETIC-2", "SYNTHETIC-2", "SYNTHETIC-UNKNOWN",
    ]
    assert "SYNTHETIC-UI-COLOR" not in repr(projected)
    assert "SYNTHETIC-UI-SOURCE" not in repr(projected)
