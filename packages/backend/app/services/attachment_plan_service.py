"""Pure attachment planning from a validated ArchiveManifest."""

from __future__ import annotations

import re
from pathlib import PurePath, PureWindowsPath
from typing import Any, Mapping

from .attachment2_plan_service import (
    ATTACHMENT2_LAYOUT_FOUR_GRID,
    ATTACHMENT2_LAYOUT_TWO_CENTERED,
    ATTACHMENT2_MAX_IMAGES_PER_PAGE,
    ATTACHMENT2_PAIR_SIZE,
    build_attachment2_pages,
    evidence_numbers,
    material_photo_groups,
    photo_values,
)
from .attachment_plan_errors_service import AttachmentPlanError
from .disc_sequence_service import parse_disc_sequence
from .attachment_plan_models_service import (
    ARCHIVE_ROWS_PAGE_KIND,
    Attachment1PagePlan,
    Attachment2State,
    Attachment3PagePlan,
    AttachmentPartRow,
    AttachmentPlan,
    AttachmentSummaryPlan,
    INSPECTOR_FINAL_PAGE_KIND,
)
from .template_profile_service import current_template_profile

PROFILE_ID = "current-template-v1"
MAX_PART_ROWS_PER_PAGE = 4
_TEMPLATE_PROFILE = current_template_profile()
_MD5_PATTERN = re.compile(r"^[0-9a-fA-F]{32}$")
_CONFIRMED_SOFTWARE = {"confirmed", "confirmed_by_report", "confirmed_by_user"}

def build_attachment_plan(
    manifest: Mapping[str, Any], report: Mapping[str, Any],
) -> AttachmentPlan:
    """Build all stage-one attachment pages without I/O or Word side effects."""
    manifest_id, parts = _validated_parts(manifest)
    source_text = _source_text(report)
    extraction_method = _extraction_method(report)
    first_disc = parts[0]["disc_number"]
    disc_result = parse_disc_sequence(first_disc)
    if not disc_result.valid or disc_result.sequence is None:
        raise AttachmentPlanError("ATTACHMENT_PLAN_INVALID", "首个光盘编号无法解析日期。")
    inspection_date = disc_result.sequence.date
    disc_numbers = tuple(str(item["disc_number"]) for item in parts)
    rows = tuple(_part_row(item, manifest) for item in parts)
    attachment1 = _attachment1_pages(rows, source_text, extraction_method)
    photos = photo_values(report)
    if len(photos) % 2:
        raise AttachmentPlanError(
            "ATTACHMENT2_IMAGE_COUNT_ODD",
            "附件图片数量必须为偶数，请补充或删除一张图片后重新导出。",
        )
    attachment2_pages = build_attachment2_pages(material_photo_groups(report))
    manifest_volume_size = _positive_int(manifest.get("volume_size_bytes"))
    attachment3 = tuple(
        Attachment3PagePlan(
            page_number=index,
            show_attachment_title=index == 1,
            part_id=str(item["part_id"]),
            part_number=int(item["part_number"]),
            filename=str(item["filename"]),
            size_bytes=int(item["size_bytes"]),
            md5=str(item["md5"]),
            disc_capacity_bytes=_positive_int(item.get("disc_capacity_bytes")),
            disc_number=str(item["disc_number"]),
            burning_date=str(item["disc_date"]),
            volume_size_bytes=manifest_volume_size,
        )
        for index, item in enumerate(parts, 1)
    )
    return AttachmentPlan(
        profile_id=PROFILE_ID,
        archive_manifest_id=manifest_id,
        attachment_summary=AttachmentSummaryPlan(
            inspection_date, len(parts), disc_numbers,
        ),
        attachment1_pages=tuple(attachment1),
            attachment2_state=Attachment2State(len(photos), "current-template-v1"),
        attachment2_pages=attachment2_pages,
        attachment3_pages=attachment3,
        diagnostics=(),
        status="ready",
    )


def _validated_parts(manifest: Mapping[str, Any]) -> tuple[str, list[Mapping[str, Any]]]:
    manifest_id = _text(manifest.get("manifest_id"))
    if not manifest_id or manifest.get("validation_status") != "validated":
        raise AttachmentPlanError("ARCHIVE_MANIFEST_INVALID", "归档清单未通过后端验证。")
    raw_parts = manifest.get("parts")
    if not isinstance(raw_parts, list) or not raw_parts:
        raise AttachmentPlanError("ARCHIVE_MANIFEST_INVALID", "归档清单必须包含实际分卷。")
    parts: list[Mapping[str, Any]] = []
    numbers: list[int] = []
    for item in raw_parts:
        if not isinstance(item, Mapping):
            raise AttachmentPlanError("ARCHIVE_MANIFEST_INVALID", "归档分卷结构无效。")
        number = item.get("part_number")
        filename = _text(item.get("filename"))
        size_bytes = item.get("size_bytes")
        md5 = _text(item.get("md5"))
        disc_date = _text(item.get("disc_date"))
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            raise AttachmentPlanError("ARCHIVE_MANIFEST_INVALID", "归档分卷序号无效。")
        if not filename or _unsafe_filename(filename):
            raise AttachmentPlanError("ARCHIVE_MANIFEST_INVALID", "归档文件名无效。")
        if (not isinstance(size_bytes, int) or isinstance(size_bytes, bool)
                or size_bytes <= 0):
            raise AttachmentPlanError("ARCHIVE_MANIFEST_INVALID", "归档分卷大小无效。")
        if not _MD5_PATTERN.fullmatch(md5):
            raise AttachmentPlanError("ARCHIVE_MANIFEST_INVALID", "归档分卷 MD5 无效。")
        if not disc_date:
            raise AttachmentPlanError("ARCHIVE_MANIFEST_INVALID", "归档分卷缺少刻录日期。")
        if not _text(item.get("part_id")) or not _text(item.get("disc_number")):
            raise AttachmentPlanError("ARCHIVE_MANIFEST_INVALID", "归档分卷缺少绑定字段。")
        disc = parse_disc_sequence(str(item["disc_number"]))
        if not disc.valid:
            raise AttachmentPlanError("ARCHIVE_MANIFEST_INVALID", "归档光盘编号无效。")
        parts.append(item)
        numbers.append(number)
    parts.sort(key=lambda item: int(item["part_number"]))
    if len(numbers) != len(set(numbers)) or [int(item["part_number"]) for item in parts] != list(range(1, len(parts) + 1)):
        raise AttachmentPlanError("ARCHIVE_MANIFEST_INVALID", "归档分卷序号不连续。")
    return manifest_id, parts


def _attachment1_pages(rows, source_text, extraction_method):
    page_chunks = [rows[index:index + MAX_PART_ROWS_PER_PAGE]
                   for index in range(0, len(rows), MAX_PART_ROWS_PER_PAGE)]
    pages = []
    for index, page_rows in enumerate(page_chunks, 1):
        is_last_data_page = index == len(page_chunks)
        signature_blank_row_count = (
            max(0, 3 - len(page_rows))
            if is_last_data_page and len(rows) < 3 else 0
        )
        pages.append(Attachment1PagePlan(
            page_number=index,
            page_kind=ARCHIVE_ROWS_PAGE_KIND,
            show_attachment_title=index == 1,
            serial_rows=tuple(page_rows),
            source_text=source_text,
            extraction_method=extraction_method,
            signature_blank_row_count=signature_blank_row_count,
        ))
    if len(rows) % MAX_PART_ROWS_PER_PAGE == 0:
        pages.append(Attachment1PagePlan(
            page_number=len(pages) + 1,
            page_kind=INSPECTOR_FINAL_PAGE_KIND,
            show_attachment_title=False,
            serial_rows=(),
            source_text=source_text,
            extraction_method=extraction_method,
            signature_blank_row_count=0,
        ))
    return pages


def _source_text(report: Mapping[str, Any]) -> str:
    values = []
    for item in (report.get("introduction") or {}).get("evidence_list") or []:
        if not isinstance(item, Mapping):
            continue
        value = _text(item.get("evidence_number"))
        if value and value not in values:
            values.append(value)
    if not values:
        raise AttachmentPlanError("ATTACHMENT_PLAN_INVALID", "缺少有效检材编号，无法生成来源。")
    return "、".join(values) + "内提取"


def _extraction_method(report: Mapping[str, Any]) -> str:
    inspection = report.get("inspection") or {}
    primary = inspection.get("primary_software")
    if not isinstance(primary, Mapping):
        raise AttachmentPlanError("ATTACHMENT_PLAN_INVALID", "主取证软件未确认。")
    name, version = _text(primary.get("name")), _text(primary.get("version"))
    if not name or not version or primary.get("confirmation_status") not in _CONFIRMED_SOFTWARE:
        raise AttachmentPlanError("ATTACHMENT_PLAN_INVALID", "主取证软件未确认。")
    runtime = {
        _text(tool.get("name")): _text(tool.get("version"))
        for tool in inspection.get("software_tools") or []
        if isinstance(tool, Mapping) and _text(tool.get("name"))
    }
    winrar = next((key for key in runtime if key.casefold() in {"winrar", "winrar压缩管理软件"}), None)
    hashlib_name = next((key for key in runtime if key.casefold() == "python hashlib"), None)
    if not winrar or not hashlib_name:
        raise AttachmentPlanError("ATTACHMENT_PLAN_INVALID", "归档工具来源未确认。")
    hardware = _text(inspection.get("hardware_device")) or "取证设备"
    return f"使用{hardware}对检材进行检查，将检出数据生成报告，然后对报告压缩并计算MD5值"


def _part_row(item: Mapping[str, Any], manifest: Mapping[str, Any]) -> AttachmentPartRow:
    return AttachmentPartRow(
        part_id=str(item["part_id"]), part_number=int(item["part_number"]),
        filename=str(item["filename"]), size_bytes=int(item["size_bytes"]),
        md5=str(item["md5"]),
        disc_capacity_bytes=_positive_int(item.get("disc_capacity_bytes")),
        volume_size_bytes=_positive_int(manifest.get("volume_size_bytes", 0)),
    )


def _positive_int(value: object) -> int:
    if value is None:
        raise AttachmentPlanError("ATTACHMENT_PLAN_INVALID", "附件计划缺少必要容量字段。")
    if isinstance(value, bool):
        raise AttachmentPlanError("ATTACHMENT_PLAN_INVALID", "附件计划容量字段类型无效。")
    if not isinstance(value, int):
        raise AttachmentPlanError("ATTACHMENT_PLAN_INVALID", "附件计划容量字段类型无效。")
    if value <= 0:
        raise AttachmentPlanError("ATTACHMENT_PLAN_INVALID", "附件计划容量字段必须为正整数。")
    return value

def _unsafe_filename(value: str) -> bool:
    return (PurePath(value).name != value or PureWindowsPath(value).name != value
            or value in {".", ".."} or "/" in value or "\\" in value)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()
