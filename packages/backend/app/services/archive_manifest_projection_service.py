"""Compatibility projection from the trusted manifest to legacy attachment DTOs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .attachment_plan_service import build_attachment_plan
from .attachment_plan_errors_service import AttachmentPlanError
from .legacy_report_projection_service import project_ordered_legacy_report


_ARCHIVE_EXTRACT_COLUMNS = (
    {"key": "no", "title": "序号", "width": "60"},
    {"key": "electronic_data", "title": "电子数据", "width": "220"},
    {"key": "source", "title": "来源", "width": "180"},
    {"key": "extraction_method", "title": "提取方式", "width": "180"},
    {"key": "md5_hash", "title": "文件MD5哈希值", "width": "260"},
)


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
        "columns": _archive_extract_columns(),
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


def project_verified_manifest_to_legacy_attachments(
    report: Mapping[str, Any], manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the persisted attachment projection for a verified archive.

    A complete review uses the same projection as Word.  Archive completion is
    also allowed before every review-only field is complete, so that path keeps
    the manifest-controlled rows and preserves any existing row context.
    """
    try:
        projected, _ = project_manifest_to_legacy_report_with_plan(report, manifest)
    except AttachmentPlanError:
        projected = _project_manifest_rows_without_review_fields(report, manifest)
    attachments = projected.get("attachments")
    if not isinstance(attachments, Mapping):
        raise AttachmentPlanError("ARCHIVE_MANIFEST_INVALID", "归档附件投影无效。")
    extract_list = attachments.get("extract_list")
    if not isinstance(extract_list, Mapping):
        raise AttachmentPlanError("ARCHIVE_MANIFEST_INVALID", "归档附件清单投影无效。")
    return {
        "disc_number": _text(attachments.get("disc_number")),
        "burning_date": _text(attachments.get("burning_date")),
        "extract_list": {
            "columns": [dict(column) for column in extract_list.get("columns", [])],
            "rows": [dict(row) for row in extract_list.get("rows", []) if isinstance(row, Mapping)],
        },
    }


def _project_manifest_rows_without_review_fields(
    report: Mapping[str, Any], manifest: Mapping[str, Any],
) -> dict[str, Any]:
    result = project_ordered_legacy_report(report)
    parts = _ordered_manifest_parts(manifest)
    attachments = result.setdefault("attachments", {})
    source = _existing_extract_value(report, "source") or _source_from_evidence(report)
    extraction_method = (
        _existing_extract_value(report, "extraction_method")
        or _hardware_extraction_method(report)
    )
    attachments["disc_number"] = _text(parts[0].get("disc_number"))
    attachments["burning_date"] = _format_date_if_possible(_text(parts[0].get("disc_date")))
    attachments["extract_list"] = {
        "columns": _archive_extract_columns(),
        "rows": [
            {
                "no": str(part["part_number"]),
                "electronic_data": _text(part.get("filename")),
                "source": source,
                "extraction_method": extraction_method,
                "md5_hash": _text(part.get("md5")),
            }
            for part in parts
        ],
    }
    return result


def _ordered_manifest_parts(manifest: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw_parts = manifest.get("parts")
    if not isinstance(raw_parts, list) or not raw_parts:
        raise AttachmentPlanError("ARCHIVE_MANIFEST_INVALID", "归档清单必须包含实际分卷。")
    parts: list[Mapping[str, Any]] = []
    for part in raw_parts:
        if not isinstance(part, Mapping):
            raise AttachmentPlanError("ARCHIVE_MANIFEST_INVALID", "归档分卷结构无效。")
        number = part.get("part_number")
        if (isinstance(number, bool) or not isinstance(number, int) or number < 1
                or not _text(part.get("filename")) or not _text(part.get("md5"))):
            raise AttachmentPlanError("ARCHIVE_MANIFEST_INVALID", "归档分卷字段无效。")
        parts.append(part)
    parts.sort(key=lambda item: int(item["part_number"]))
    if [int(item["part_number"]) for item in parts] != list(range(1, len(parts) + 1)):
        raise AttachmentPlanError("ARCHIVE_MANIFEST_INVALID", "归档分卷序号不连续。")
    return parts


def _existing_extract_value(report: Mapping[str, Any], key: str) -> str:
    attachments = report.get("attachments")
    extract_list = attachments.get("extract_list") if isinstance(attachments, Mapping) else None
    rows = extract_list.get("rows") if isinstance(extract_list, Mapping) else None
    if not isinstance(rows, list):
        return ""
    for row in rows:
        if isinstance(row, Mapping) and _text(row.get(key)):
            return _text(row.get(key))
    return ""


def _source_from_evidence(report: Mapping[str, Any]) -> str:
    introduction = report.get("introduction")
    evidence = introduction.get("evidence_list") if isinstance(introduction, Mapping) else None
    values = []
    if isinstance(evidence, list):
        for item in evidence:
            value = _text(item.get("evidence_number")) if isinstance(item, Mapping) else ""
            if value and value not in values:
                values.append(value)
    return "、".join(values) + "内提取" if values else ""


def _hardware_extraction_method(report: Mapping[str, Any]) -> str:
    inspection = report.get("inspection")
    hardware = (
        _text(inspection.get("hardware_device"))
        if isinstance(inspection, Mapping) else ""
    ) or "取证设备"
    return f"使用{hardware}对检材进行检查，将检出数据生成报告，然后对报告压缩并计算MD5值"


def _archive_extract_columns() -> list[dict[str, str]]:
    return [dict(column) for column in _ARCHIVE_EXTRACT_COLUMNS]


def _format_date(value: str) -> str:
    year, month, day = value.split("-")
    return f"{year}年{int(month)}月{int(day)}日"


def _format_date_if_possible(value: str) -> str:
    try:
        return _format_date(value)
    except (AttributeError, TypeError, ValueError):
        return value


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else "" if value is None else str(value).strip()
