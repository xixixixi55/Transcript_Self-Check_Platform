"""Manifest authority and legacy projection regression tests."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.archive_manifest_projection_service import (  # noqa: E402
    project_manifest_to_legacy_report,
    project_verified_manifest_to_legacy_attachments,
)
from app.repository.archive_report_metadata_repository import (  # noqa: E402
    apply_verified_archive_result,
)


def report():
    return {
        "introduction": {
            "evidence_list": [{"evidence_number": "JC-A"}],
            "inspector_snapshots": [],
        },
        "inspection": {
            "hardware_device": "测试设备",
            "primary_software": {
                "name": "主取证软件", "version": "1.0",
                "confirmation_status": "confirmed_by_report",
            },
            "software_tools": [
                {"name": "WinRAR压缩管理软件", "version": "6.24"},
                {"name": "Python hashlib", "version": "3.12"},
            ],
        },
        "attachments": {
            "disc_number": "GP20260101-99",
            "burning_date": "1900年1月1日",
            "extract_list": {"rows": [{"electronic_data": "client.rar", "md5_hash": "client"}]},
        },
    }


def manifest():
    return {
        "manifest_id": "trusted-manifest",
        "validation_status": "validated",
        "volume_size_bytes": 4_000_000_000,
        "parts": [
            {
                "part_id": "part-1", "part_number": 1,
                "filename": "server.part1.rar", "md5": "1" * 32,
                "size_bytes": 100,
                "disc_number": "GP20260706-01", "disc_date": "2026-07-06",
                "disc_capacity_bytes": 4_000_000_000,
                "volume_size_bytes": 4_000_000_000,
            },
            {
                "part_id": "part-2", "part_number": 2,
                "filename": "server.part2.rar", "md5": "2" * 32,
                "size_bytes": 200,
                "disc_number": "GP20260706-02", "disc_date": "2026-07-06",
                "disc_capacity_bytes": 4_000_000_000,
                "volume_size_bytes": 4_000_000_000,
            },
        ],
    }


def test_client_attachment_fields_are_rebuilt_from_trusted_manifest():
    projected = project_manifest_to_legacy_report(report(), manifest())
    attachments = projected["attachments"]
    assert attachments["disc_number"] == "GP20260706-01"
    assert attachments["burning_date"] == "2026年7月6日"
    assert [row["electronic_data"] for row in attachments["extract_list"]["rows"]] == [
        "server.part1.rar", "server.part2.rar",
    ]
    assert [row["md5_hash"] for row in attachments["extract_list"]["rows"]] == [
        "1" * 32, "2" * 32,
    ]


def test_projection_does_not_add_absolute_paths_or_manifest_as_client_data():
    projected = project_manifest_to_legacy_report(report(), manifest())
    serialized = repr(projected)
    assert "client.rar" not in serialized
    assert "C:\\" not in serialized
    assert "manifest_id" not in projected["attachments"]


def test_verified_attachment_projection_keeps_ordered_manifest_rows_without_size_column():
    projection = project_verified_manifest_to_legacy_attachments(report(), manifest())
    table = projection["extract_list"]
    assert [row["no"] for row in table["rows"]] == ["1", "2"]
    assert [row["electronic_data"] for row in table["rows"]] == [
        "server.part1.rar", "server.part2.rar",
    ]
    assert [row["md5_hash"] for row in table["rows"]] == ["1" * 32, "2" * 32]
    assert "file_size" not in {column["key"] for column in table["columns"]}
    assert all("file_size" not in row for row in table["rows"])


def test_verified_attachment_projection_fills_extraction_method_before_review_is_complete():
    incomplete = report()
    incomplete["inspection"].pop("primary_software")
    incomplete["attachments"]["extract_list"] = {
        "rows": [{"source": "JC-A内提取", "extraction_method": ""}],
    }

    projection = project_verified_manifest_to_legacy_attachments(incomplete, manifest())

    assert {
        row["extraction_method"] for row in projection["extract_list"]["rows"]
    } == {
        "使用测试设备对检材进行检查，将检出数据生成报告，然后对报告压缩并计算MD5值",
    }
    assert {row["source"] for row in projection["extract_list"]["rows"]} == {
        "JC-A检材内提取",
    }


def test_verified_manifest_backfills_existing_report_result_fields():
    projected = apply_verified_archive_result(report(), manifest())
    result = projected["inspection"]["result"]
    assert result == {
        "rar_filename": "server.part1.rar、server.part2.rar",
        "md5_hash": "1" * 32 + "、" + "2" * 32,
        "file_size": "100、200",
    }
    assert "manifest_id" not in result
