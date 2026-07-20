"""Pure AttachmentPlan boundaries and deterministic pagination tests."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.attachment_plan_service import AttachmentPlanError, build_attachment_plan  # noqa: E402


def report(inspector_count=2, evidence_numbers=None):
    numbers = evidence_numbers or ["JC-A", "JC-B", "JC-C"]
    return {
        "introduction": {
            "evidence_list": [{"evidence_number": value} for value in numbers],
            "inspector_snapshots": [
                {"unit": "单位", "name": f"人员{index}", "police_number": f"P{index}"}
                for index in range(inspector_count)
            ],
        },
        "inspection": {
            "primary_software": {
                "name": "主取证软件", "version": "1.0",
                "confirmation_status": "confirmed_by_user",
            },
            "software_tools": [
                {"name": "WinRAR压缩管理软件", "version": "6.24"},
                {"name": "Python hashlib", "version": "3.12"},
            ],
        },
        "attachments": {"photo_ids": []},
    }


def manifest(count, *, start=1):
    return {
        "manifest_id": "manifest-synthetic",
        "validation_status": "validated",
        "parts": [
            {
                "part_id": f"part-{number}", "part_number": number,
                "filename": f"case.part{number}.rar",
                "md5": f"{number:032x}",
                "disc_number": f"GP20260706-{start + number - 1:02d}",
                "disc_date": "2026-07-06",
            }
            for number in range(1, count + 1)
        ],
    }


@pytest.mark.parametrize(
    ("count", "row_counts"),
    [(1, [1]), (2, [1, 1]), (4, [3, 1]), (5, [4, 1]),
     (8, [4, 3, 1]), (9, [4, 4, 1])],
)
def test_attachment1_reserves_final_template_signature_row(count, row_counts):
    plan = build_attachment_plan(manifest(count), report(0))
    assert [len(page.serial_rows) for page in plan.attachment1_pages] == row_counts
    rows = [row for page in plan.attachment1_pages for row in page.serial_rows]
    assert [row.part_number for row in rows] == list(range(1, count + 1))
    assert all(page.page_kind == "archive_rows" for page in plan.attachment1_pages)
    assert [page.show_attachment_title for page in plan.attachment1_pages] == [True] + [False] * (len(row_counts) - 1)
    assert plan.attachment_summary.inspection_date == "2026-07-06"


def test_attachment1_has_complete_source_and_method_on_every_page():
    plan = build_attachment_plan(manifest(5), report(20, ["JC-A", "", "JC-A", "JC-B"]))
    assert all(page.source_text == "JC-A、JC-B内提取" for page in plan.attachment1_pages)
    assert all("主取证软件" in page.extraction_method for page in plan.attachment1_pages)
    assert all("WinRAR压缩管理软件" in page.extraction_method for page in plan.attachment1_pages)
    assert all("Python hashlib" in page.extraction_method for page in plan.attachment1_pages)


@pytest.mark.parametrize("inspector_count", [0, 1, 4, 5, 8, 20, 21])
def test_inspectors_do_not_change_attachment1_plan_or_create_overflow(inspector_count):
    plan = build_attachment_plan(manifest(5), report(inspector_count))
    assert [len(page.serial_rows) for page in plan.attachment1_pages] == [4, 1]
    assert all(page.page_kind == "archive_rows" for page in plan.attachment1_pages)
    assert not any(page.page_kind == "inspector_final" for page in plan.attachment1_pages)


def test_attachment3_is_one_page_per_manifest_part_and_uses_manifest_values():
    value = manifest(3)
    value["parts"][1]["disc_date"] = "2026-07-07"
    plan = build_attachment_plan(value, report())
    assert len(plan.attachment3_pages) == 3
    assert [page.filename for page in plan.attachment3_pages] == [
        "case.part1.rar", "case.part2.rar", "case.part3.rar",
    ]
    assert [page.md5 for page in plan.attachment3_pages] == [f"{i:032x}" for i in (1, 2, 3)]
    assert [page.disc_number for page in plan.attachment3_pages] == [
        "GP20260706-01", "GP20260706-02", "GP20260706-03",
    ]
    assert [page.burning_date for page in plan.attachment3_pages] == [
        "2026-07-06", "2026-07-07", "2026-07-06",
    ]
    assert [page.show_attachment_title for page in plan.attachment3_pages] == [True, False, False]


@pytest.mark.parametrize("bad_manifest", [
    {"manifest_id": "empty", "validation_status": "validated", "parts": []},
    {"manifest_id": "missing-md5", "validation_status": "validated", "parts": [{
        "part_id": "p1", "part_number": 1, "filename": "case.part1.rar",
        "md5": "", "disc_number": "GP20260706-01",
    }]},
])
def test_invalid_manifest_is_rejected(bad_manifest):
    with pytest.raises(AttachmentPlanError) as error:
        build_attachment_plan(bad_manifest, report())
    assert error.value.code in {"ARCHIVE_MANIFEST_INVALID", "ATTACHMENT_PLAN_INVALID"}


def test_numeric_part_order_and_no_absolute_paths():
    value = manifest(2)
    value["parts"] = [value["parts"][1], value["parts"][0]]
    plan = build_attachment_plan(value, report())
    assert [row.part_number for page in plan.attachment1_pages for row in page.serial_rows] == [1, 2]
    assert all(":" not in row.filename for page in plan.attachment1_pages for row in page.serial_rows)


def test_old_attachment_fields_cannot_replace_manifest_values():
    value = manifest(1)
    current_report = report()
    current_report["attachments"]["extract_list"] = {"rows": [{
        "no": "99", "electronic_data": "client.rar", "md5_hash": "client-md5",
    }]}
    plan = build_attachment_plan(value, current_report)
    row = plan.attachment1_pages[0].serial_rows[0]
    assert row.filename == "case.part1.rar"
    assert row.md5 == "00000000000000000000000000000001"
