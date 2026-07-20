"""Manifest authority and legacy projection regression tests."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.archive_manifest_projection_service import (  # noqa: E402
    project_manifest_to_legacy_report,
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
        "parts": [
            {
                "part_id": "part-1", "part_number": 1,
                "filename": "server.part1.rar", "md5": "1" * 32,
                "size_bytes": 100,
                "disc_number": "GP20260706-01", "disc_date": "2026-07-06",
            },
            {
                "part_id": "part-2", "part_number": 2,
                "filename": "server.part2.rar", "md5": "2" * 32,
                "size_bytes": 200,
                "disc_number": "GP20260706-02", "disc_date": "2026-07-06",
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
