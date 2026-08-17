"""Pure AttachmentPlan boundaries and deterministic pagination tests."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.attachment_plan_service import AttachmentPlanError, build_attachment_plan  # noqa: E402
from app.services.attachment2_plan_service import with_compatible_material_photo_groups  # noqa: E402


def report(inspector_count=2, evidence_numbers=None, photo_ids=None, photo_groups=None):
    numbers = evidence_numbers or ["JC-A", "JC-B", "JC-C", "JC-D", "JC-E"]
    evidence_list = [
        {"id": f"material-{index + 1}", "evidence_number": value}
        for index, value in enumerate(numbers)
    ]
    if photo_ids and photo_groups is None:
        photo_groups = [
            {
                "material_id": evidence_list[index]["id"],
                "material_number": evidence_list[index]["evidence_number"],
                "display_text": f"检材{evidence_list[index]['evidence_number']}照片",
                "ordered_image_ids": photo_ids[index * 2:index * 2 + 2],
                "source_order": index + 1,
            }
            for index in range(len(photo_ids) // 2)
        ]
    return {
        "introduction": {
            "evidence_list": evidence_list,
            "inspector_snapshots": [
                {"unit": "单位", "name": f"人员{index}", "police_number": f"P{index}"}
                for index in range(inspector_count)
            ],
        },
        "inspection": {
            "hardware_device": "测试设备",
            "primary_software": {
                "name": "主取证软件", "version": "1.0",
                "confirmation_status": "confirmed_by_user",
            },
            "software_tools": [
                {"name": "WinRAR压缩管理软件", "version": "6.24"},
                {"name": "Python hashlib", "version": "3.12"},
            ],
        },
        "attachments": {"photo_ids": photo_ids or [], "photo_groups": photo_groups or []},
    }


def manifest(count, *, start=1):
    return {
        "manifest_id": "manifest-synthetic",
        "validation_status": "validated",
        "volume_size_bytes": 4_000_000_000,
        "parts": [
            {
                "part_id": f"part-{number}", "part_number": number,
                "filename": f"case.part{number}.rar",
                "size_bytes": number * 100,
                "md5": f"{number:032x}",
                "disc_number": f"GP20260706-{start + number - 1:02d}",
                "disc_date": "2026-07-06",
                "disc_capacity_bytes": 4_000_000_000,
                "volume_size_bytes": 4_000_000_000,
            }
            for number in range(1, count + 1)
        ],
    }


def test_oversized_single_manifest_keeps_non_applicable_capacities_empty():
    oversized = {
        "manifest_id": "manifest-oversized",
        "validation_status": "validated",
        "archive_mode": "oversized_single",
        "volume_size_bytes": None,
        "parts": [{
            "part_id": "part-oversized", "part_number": 1,
            "filename": "case.rar", "size_bytes": 46 * 1024 ** 3,
            "md5": "a" * 32, "disc_number": "GP20260706-01",
            "disc_date": "2026-07-06", "disc_capacity_bytes": None,
            "volume_size_bytes": None,
        }],
    }
    plan = build_attachment_plan(oversized, report(0))
    row = plan.attachment1_pages[0].serial_rows[0]
    page = plan.attachment3_pages[0]
    assert row.disc_capacity_bytes is None
    assert row.volume_size_bytes is None
    assert page.disc_capacity_bytes is None
    assert page.volume_size_bytes is None


def test_missing_legacy_photo_groups_are_rebuilt_from_material_and_image_order():
    photo_ids = ["asset-synthetic-front", "asset-synthetic-back"]
    value = report(evidence_numbers=["SYNTHETIC-1"], photo_ids=photo_ids)
    value["attachments"].pop("photo_groups")

    compatible = with_compatible_material_photo_groups(value)

    assert compatible["attachments"]["photo_groups"] == [{
        "material_id": "material-1",
        "material_number": "SYNTHETIC-1",
        "display_text": "检材SYNTHETIC-1照片",
        "ordered_image_ids": photo_ids,
        "source_order": 1,
    }]
    assert "photo_groups" not in value["attachments"]


@pytest.mark.parametrize(
    ("count", "row_counts", "page_kinds"),
    [
        (1, [1], ["archive_rows"]),
        (2, [2], ["archive_rows"]),
        (3, [3], ["archive_rows"]),
        (4, [4, 0], ["archive_rows", "inspector_final"]),
        (5, [4, 1], ["archive_rows", "archive_rows"]),
        (8, [4, 4, 0], ["archive_rows", "archive_rows", "inspector_final"]),
        (9, [4, 4, 1], ["archive_rows", "archive_rows", "archive_rows"]),
    ],
)
def test_attachment1_uses_manifest_rows_with_four_row_page_limit(
    count, row_counts, page_kinds,
):
    plan = build_attachment_plan(manifest(count), report(0))
    assert [len(page.serial_rows) for page in plan.attachment1_pages] == row_counts
    rows = [row for page in plan.attachment1_pages for row in page.serial_rows]
    assert [row.part_number for row in rows] == list(range(1, count + 1))
    assert [page.page_kind for page in plan.attachment1_pages] == page_kinds
    assert [page.signature_blank_row_count for page in plan.attachment1_pages] == (
        [2] if count == 1 else [1] if count == 2 else [0] * len(row_counts)
    )
    assert [page.show_attachment_title for page in plan.attachment1_pages] == [True] + [False] * (len(row_counts) - 1)
    assert plan.attachment_summary.inspection_date == "2026-07-06"


def test_attachment1_has_complete_source_and_method_on_every_page():
    plan = build_attachment_plan(manifest(5), report(20, ["JC-A", "", "JC-A", "JC-B"]))
    assert all(page.source_text == "JC-A、JC-B检材内提取" for page in plan.attachment1_pages)
    assert all("使用测试设备对检材进行检查" in page.extraction_method for page in plan.attachment1_pages)
    assert all("将检出数据生成报告" in page.extraction_method for page in plan.attachment1_pages)


@pytest.mark.parametrize("inspector_count", [0, 1, 4, 5, 8, 20, 21])
def test_inspectors_do_not_change_attachment1_plan_or_create_overflow(inspector_count):
    plan = build_attachment_plan(manifest(5), report(inspector_count))
    assert [len(page.serial_rows) for page in plan.attachment1_pages] == [4, 1]
    assert all(page.page_kind == "archive_rows" for page in plan.attachment1_pages)
    assert not any(page.page_kind == "inspector_final" for page in plan.attachment1_pages)


def test_four_manifest_rows_reserve_a_new_signature_page():
    plan = build_attachment_plan(manifest(4), report(0))
    assert [len(page.serial_rows) for page in plan.attachment1_pages] == [4, 0]
    assert plan.attachment1_pages[-1].page_kind == "inspector_final"


def test_attachment3_is_one_page_per_manifest_part_and_uses_manifest_values():
    value = manifest(3)
    value["parts"][1]["disc_date"] = "2026-07-07"
    plan = build_attachment_plan(value, report())
    assert len(plan.attachment3_pages) == 3
    assert [page.filename for page in plan.attachment3_pages] == [
        "case.part1.rar", "case.part2.rar", "case.part3.rar",
    ]
    assert [page.md5 for page in plan.attachment3_pages] == [f"{i:032x}" for i in (1, 2, 3)]
    assert [page.size_bytes for page in plan.attachment3_pages] == [100, 200, 300]
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


def test_hashmyfiles_runtime_tool_satisfies_archive_tool_source():
    current = report(0)
    current["inspection"]["software_tools"] = [
        {"name": "WinRAR压缩管理软件", "version": "6.24"},
        {"name": "HashMyFiles", "version": "2.51"},
    ]
    plan = build_attachment_plan(manifest(1), current)
    assert plan.attachment1_pages
    assert all(
        "计算MD5值" in page.extraction_method
        for page in plan.attachment1_pages
    )


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
    assert row.size_bytes == 100


@pytest.mark.parametrize("photo_count", [0, 2, 4, 6, 8, 10])
def test_attachment2_pages_use_pair_layouts_and_are_deterministic(photo_count):
    photo_ids = [f"image-{index}" for index in range(1, photo_count + 1)]
    evidence_numbers = [f"JC-{chr(65 + index)}" for index in range(photo_count // 2)]
    first = build_attachment_plan(
        manifest(1), report(evidence_numbers=evidence_numbers, photo_ids=photo_ids),
    )
    second = build_attachment_plan(
        manifest(1), report(evidence_numbers=evidence_numbers, photo_ids=photo_ids),
    )
    assert first == second
    assert len(first.attachment2_pages) == ((photo_count + 3) // 4 if photo_count else 0)
    assert [page.show_attachment_title for page in first.attachment2_pages] == (
        [True] + [False] * (len(first.attachment2_pages) - 1)
        if photo_count else []
    )
    expected_page_sizes = {
        0: [], 2: [2], 4: [4], 6: [4, 2], 8: [4, 4], 10: [4, 4, 2],
    }[photo_count]
    assert [len(page.images) for page in first.attachment2_pages] == expected_page_sizes
    assert [page.layout for page in first.attachment2_pages] == [
        "two_centered" if size == 2 else "four_grid"
        for size in expected_page_sizes
    ]
    expected_evidence = {
        0: [],
        2: [("JC-A",)],
        4: [("JC-A", "JC-B")],
        6: [("JC-A", "JC-B"), ("JC-C",)],
        8: [("JC-A", "JC-B"), ("JC-C", "JC-D")],
        10: [("JC-A", "JC-B"), ("JC-C", "JC-D"), ("JC-E",)],
    }[photo_count]
    assert [page.evidence_numbers for page in first.attachment2_pages] == expected_evidence
    planned = [image for page in first.attachment2_pages for image in page.images]
    assert [image.source_image_id for image in planned] == photo_ids
    if first.attachment2_pages:
        assert [image.slot for image in first.attachment2_pages[0].images] == (
            ["left", "right"] if photo_count == 2
            else ["top-left", "top-right", "bottom-left", "bottom-right"]
        )
    assert all(
        all(separator not in image.safe_display_name for separator in ("/", "\\", ":"))
        for image in planned
    )


@pytest.mark.parametrize("photo_count", [1, 3, 5])
def test_attachment2_odd_image_counts_are_stably_blocked(photo_count):
    with pytest.raises(AttachmentPlanError) as error:
        build_attachment_plan(
            manifest(1),
            report(photo_ids=[f"C:\\case\\photo-{index}.png" for index in range(photo_count)]),
        )
    assert error.value.code == "ATTACHMENT2_IMAGE_COUNT_ODD"
    assert "图片数量必须为偶数" in error.value.safe_message
    assert "C:\\" not in error.value.safe_message


def test_attachment2_plan_never_exposes_client_path_values():
    plan = build_attachment_plan(
        manifest(1),
        report(
            evidence_numbers=["JC-A"],
            photo_ids=[r"C:\case\横图.png", r"D:/case/竖图.png"],
        ),
    )
    serialized = repr(plan)
    assert "C:\\case" not in serialized
    assert "D:/case" not in serialized
    assert [image.source_image_id for page in plan.attachment2_pages for image in page.images] == [
        "photo-1", "photo-2"
    ]


@pytest.mark.parametrize("bad_group", [
    {"material_id": "material-1", "material_number": "JC-A", "display_text": "检材JC-A照片",
     "ordered_image_ids": ["photo-1"], "source_order": 1},
    {"material_id": "material-1", "material_number": "JC-A", "display_text": "检材JC-A照片",
     "ordered_image_ids": ["photo-1", "photo-2", "photo-3"], "source_order": 1},
    {"material_id": "missing", "material_number": "JC-A", "display_text": "检材JC-A照片",
     "ordered_image_ids": ["photo-1", "photo-2"], "source_order": 1},
    {"material_id": "material-1", "material_number": "", "display_text": "检材照片",
     "ordered_image_ids": ["photo-1", "photo-2"], "source_order": 1},
])
def test_attachment2_rejects_invalid_explicit_material_mapping(bad_group):
    with pytest.raises(AttachmentPlanError) as error:
        build_attachment_plan(
            manifest(1),
            report(
                evidence_numbers=["JC-A"],
                photo_ids=["photo-1", "photo-2"],
                photo_groups=[bad_group],
            ),
        )
    assert error.value.code in {
        "ATTACHMENT2_MATERIAL_IMAGE_COUNT_INVALID",
        "ATTACHMENT2_IMAGE_MAPPING_INVALID",
    }


def test_attachment2_rejects_cross_material_or_reordered_photo_mapping():
    with pytest.raises(AttachmentPlanError) as error:
        build_attachment_plan(
            manifest(1),
            report(
                evidence_numbers=["JC-A", "JC-B"],
                photo_ids=["photo-1", "photo-2", "photo-3", "photo-4"],
                photo_groups=[
                    {"material_id": "material-1", "material_number": "JC-A",
                     "display_text": "检材JC-A照片", "ordered_image_ids": ["photo-1", "photo-3"],
                     "source_order": 1},
                    {"material_id": "material-2", "material_number": "JC-B",
                     "display_text": "检材JC-B照片", "ordered_image_ids": ["photo-2", "photo-4"],
                     "source_order": 2},
                ],
            ),
        )
    assert error.value.code == "ATTACHMENT2_IMAGE_MAPPING_INVALID"
