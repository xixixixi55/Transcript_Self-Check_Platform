"""单一保存顺序旧版投影的 SYNTHETIC T010 覆盖测试。"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.attachment_plan_service import build_attachment_plan  # noqa: E402
from app.services.archive_manifest_projection_service import project_manifest_to_legacy_report_with_plan  # noqa: E402
from app.services.document_builder_service import build_record_document  # noqa: E402
from app.services.legacy_report_projection_service import project_ordered_legacy_report  # noqa: E402
from synthetic_report_builders import build_ordered_report  # noqa: E402


def _manifest():
    return {"manifest_id": "SYNTHETIC-MANIFEST", "validation_status": "validated", "volume_size_bytes": 4_000_000_000, "parts": [
        {"part_id": "SYNTHETIC-PART-1", "part_number": 1, "filename": "SYNTHETIC.part1.rar", "size_bytes": 100, "md5": "1" * 32, "disc_number": "GP20260706-01", "disc_date": "2026-07-06", "disc_capacity_bytes": 4_000_000_000},
    ]}


def test_saved_drag_order_drives_body_attachment_plan_and_person_snapshot_projection():
    projected = project_ordered_legacy_report(build_ordered_report())
    plan = build_attachment_plan(_manifest(), projected)
    manifest_report, manifest_plan = project_manifest_to_legacy_report_with_plan(
        build_ordered_report(), _manifest(),
    )
    commands = build_record_document(projected)
    paragraphs = "\n".join(
        item.get("props", {}).get("text", "") for item in commands if item.get("type") == "paragraph"
    )

    assert [item["evidence_number"] for item in projected["introduction"]["evidence_list"]] == ["SYNTHETIC-10", "SYNTHETIC-2"]
    assert [item["name"] for item in projected["introduction"]["inspectors"]] == ["SYNTHETIC-B", "SYNTHETIC-A"]
    assert [item["material_number"] for item in projected["attachments"]["photo_groups"]] == ["SYNTHETIC-10", "SYNTHETIC-2"]
    assert projected["attachments"]["photo_ids"] == ["photo-10a", "photo-10b", "photo-2a", "photo-2b"]
    assert plan.attachment1_pages[0].source_text == "SYNTHETIC-10、SYNTHETIC-2检材内提取"
    assert [page.inspection_result_material_numbers for page in plan.attachment2_pages] == [("SYNTHETIC-10", "SYNTHETIC-2")]
    assert manifest_plan == plan
    assert manifest_report["attachments"]["extract_list"]["rows"][0]["source"] == "SYNTHETIC-10、SYNTHETIC-2检材内提取"
    assert manifest_plan.attachment3_pages[0].filename == "SYNTHETIC.part1.rar"
    assert "经对编号为SYNTHETIC-10、SYNTHETIC-2号检材使用" in paragraphs
    assert paragraphs.index("SYNTHETIC-B") < paragraphs.index("SYNTHETIC-A")
    assert "SYNTHETIC-LIBRARY-STALE" not in paragraphs


def test_duplicate_or_unrecognizable_numbers_are_never_resorted_downstream():
    report = build_ordered_report()
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
