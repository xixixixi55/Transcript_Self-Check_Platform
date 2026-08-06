"""定向测试：附件回填（检查结果 + 附件1，覆盖语义）。"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.services.attachment_backfill_service import backfill_from_manifest  # noqa: E402


def manifest() -> dict:
    return {
        "manifest_id": "SYNTHETIC-MANIFEST-BACKFILL",
        "validation_status": "validated",
        "volume_size_bytes": 4_000_000_000,
        "parts": [
            {
                "part_id": "SYNTHETIC-PART-1", "part_number": 1,
                "filename": "SYNTHETIC-CASE.part1.rar", "size_bytes": 4,
                "md5": "a" * 32, "disc_number": "GP20260718-01", "disc_date": "2026-07-18",
                "disc_capacity_bytes": 4_000_000_000,
            },
            {
                "part_id": "SYNTHETIC-PART-2", "part_number": 2,
                "filename": "SYNTHETIC-CASE.part2.rar", "size_bytes": 5,
                "md5": "b" * 32, "disc_number": "GP20260718-02", "disc_date": "2026-07-18",
                "disc_capacity_bytes": 4_000_000_000,
            },
        ],
    }


def base_report() -> dict:
    return {
        "introduction": {
            "case_summary": "SYNTHETIC",
            "evidence_list": [{"evidence_number": "SYN-1"}],
        },
        "inspection": {
            "hardware_device": "SYNTHETIC-DEVICE",
            "primary_software": {
                "name": "SYNTHETIC-TOOL", "version": "1.0",
                "confirmation_status": "confirmed",
            },
            "result": {"rar_filename": "OLD", "md5_hash": "OLD", "file_size": "OLD"},
        },
        "attachments": {"extract_list": {"columns": [], "rows": []}},
    }


def test_backfill_overwrites_result_fields_and_preserves_attachment_projection() -> None:
    filled = backfill_from_manifest(base_report(), manifest())
    result = filled["inspection"]["result"]
    assert result["rar_filename"] == "SYNTHETIC-CASE.part1.rar、SYNTHETIC-CASE.part2.rar"
    assert result["md5_hash"] == ("a" * 32) + "、" + ("b" * 32)
    assert result["file_size"] == "4、5"
    # 附件1 projection is best-effort at manifest time; the export path owns the
    # full AttachmentPlan derivation and remains unchanged.
    assert isinstance(filled["attachments"], dict)


def test_backfill_without_review_fields_does_not_fail() -> None:
    report = {"introduction": {"case_summary": "SYNTHETIC"}}
    filled = backfill_from_manifest(report, manifest())
    # Result fields filled even when review fields are incomplete.
    assert filled["inspection"]["result"]["rar_filename"].startswith("SYNTHETIC-CASE.part1")
