"""Compatibility projection from the trusted manifest to legacy attachment DTOs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .attachment_plan_service import build_attachment_plan
from .legacy_report_projection_service import project_ordered_legacy_report


def project_manifest_to_legacy_report(
    report: Mapping[str, Any], manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Regenerate old attachment fields; manifest values always win."""
    result, _ = project_manifest_to_legacy_report_with_plan(report, manifest)
    return result


def project_manifest_to_legacy_report_with_plan(
    report: Mapping[str, Any], manifest: Mapping[str, Any],
) -> tuple[dict[str, Any], Any]:
    """Return the same legacy projection and the already-built formal plan."""
    result = project_ordered_legacy_report(report)
    plan = build_attachment_plan(manifest, result)
    attachments = result.setdefault("attachments", {})
    attachments["disc_number"] = plan.attachment_summary.disc_numbers[0]
    attachments["burning_date"] = _format_date(plan.attachment_summary.inspection_date)
    attachments["extract_list"] = {
        "columns": [
            {"key": "no", "title": "序号", "width": "60"},
            {"key": "electronic_data", "title": "电子数据", "width": "220"},
            {"key": "source", "title": "来源", "width": "180"},
            {"key": "extraction_method", "title": "提取方式", "width": "180"},
            {"key": "md5_hash", "title": "文件MD5哈希值", "width": "260"},
        ],
        "rows": [
            {
                "no": str(row.part_number),
                "electronic_data": row.filename,
                "source": plan.attachment1_pages[0].source_text,
                "extraction_method": plan.attachment1_pages[0].extraction_method,
                "md5_hash": row.md5,
            }
            for page in plan.attachment1_pages for row in page.serial_rows
        ],
    }
    return result, plan


def _format_date(value: str) -> str:
    year, month, day = value.split("-")
    return f"{year}年{int(month)}月{int(day)}日"
