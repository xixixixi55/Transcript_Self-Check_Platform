"""根据已验证 ArchiveManifest 进行纯附件规划。"""

from __future__ import annotations

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
from .disc_sequence_service import (
    archive_medium_for_mode, parse_archive_medium_sequence,
)
from .attachment_plan_models_service import (
    ARCHIVE_ROWS_PAGE_KIND,
    AttachmentPlanError,
    Attachment1PagePlan,
    Attachment2State,
    Attachment3PagePlan,
    AttachmentPartRow,
    AttachmentPlan,
    AttachmentSummaryPlan,
    INSPECTOR_FINAL_PAGE_KIND,
)
from .template_profile_service import current_template_profile
from .legacy_report_projection_service import project_ordered_legacy_report
from .hash_algorithm_service import (
    hash_extraction_method,
    manifest_part_business_hash,
)

PROFILE_ID = "current-template-v1"
MAX_PART_ROWS_PER_PAGE = 4
_TEMPLATE_PROFILE = current_template_profile()
_CONFIRMED_SOFTWARE = {"confirmed", "confirmed_by_report", "confirmed_by_user"}

def build_attachment_plan(
    manifest: Mapping[str, Any], report: Mapping[str, Any],
) -> AttachmentPlan:
    """构建所有阶段一附件页面，不产生 I/O 或 Word 副作用。"""
    report = project_ordered_legacy_report(report)
    manifest_id, parts = _validated_parts(manifest)
    hash_algorithm, _ = manifest_part_business_hash(parts[0])
    archive_mode = str(manifest.get("archive_mode") or "standard_split")
    archive_medium = archive_medium_for_mode(archive_mode)
    if archive_medium == "hard_drive" and len(parts) != 1:
        raise AttachmentPlanError(
            "ARCHIVE_MANIFEST_INVALID", "硬盘归档必须只有一个完整压缩包。",
        )
    source_text = _source_text(report)
    extraction_method = _extraction_method(report, hash_algorithm)
    first_disc = parts[0]["disc_number"]
    disc_result = parse_archive_medium_sequence(first_disc, archive_mode)
    if not disc_result.valid or disc_result.sequence is None:
        medium_label = "硬盘编号" if archive_medium == "hard_drive" else "首个光盘编号"
        raise AttachmentPlanError("ATTACHMENT_PLAN_INVALID", f"{medium_label}无法解析日期。")
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
    oversized_single = manifest.get("archive_mode") == "oversized_single_volume"
    manifest_volume_size = _capacity_value(
        manifest.get("volume_size_bytes"), optional=oversized_single,
    )
    attachment3 = tuple(
        Attachment3PagePlan(
            page_number=index,
            show_attachment_title=index == 1,
            part_id=str(item["part_id"]),
            part_number=int(item["part_number"]),
            filename=str(item["filename"]),
            size_bytes=int(item["size_bytes"]),
            md5=manifest_part_business_hash(item)[1].upper(),
            disc_capacity_bytes=_capacity_value(
                item.get("disc_capacity_bytes"), optional=oversized_single,
            ),
            disc_number=str(item["disc_number"]),
            burning_date=str(item["disc_date"]),
            volume_size_bytes=manifest_volume_size,
        )
        for index, item in enumerate(parts, 1)
    )
    return AttachmentPlan(
        profile_id=PROFILE_ID,
        archive_manifest_id=manifest_id,
        hash_algorithm=hash_algorithm,
        archive_medium=archive_medium,
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
        disc_date = _text(item.get("disc_date"))
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            raise AttachmentPlanError("ARCHIVE_MANIFEST_INVALID", "归档分卷序号无效。")
        if not filename or _unsafe_filename(filename):
            raise AttachmentPlanError("ARCHIVE_MANIFEST_INVALID", "归档文件名无效。")
        if (not isinstance(size_bytes, int) or isinstance(size_bytes, bool)
                or size_bytes <= 0):
            raise AttachmentPlanError("ARCHIVE_MANIFEST_INVALID", "归档分卷大小无效。")
        try:
            hash_algorithm, _ = manifest_part_business_hash(item)
        except ValueError as error:
            raise AttachmentPlanError("ARCHIVE_MANIFEST_INVALID", str(error)) from error
        if not disc_date:
            raise AttachmentPlanError("ARCHIVE_MANIFEST_INVALID", "归档分卷缺少刻录日期。")
        if not _text(item.get("part_id")) or not _text(item.get("disc_number")):
            raise AttachmentPlanError("ARCHIVE_MANIFEST_INVALID", "归档分卷缺少绑定字段。")
        archive_mode = str(manifest.get("archive_mode") or "standard_split")
        disc = parse_archive_medium_sequence(str(item["disc_number"]), archive_mode)
        if not disc.valid:
            raise AttachmentPlanError("ARCHIVE_MANIFEST_INVALID", "归档介质编号无效。")
        parts.append(item)
        numbers.append(number)
        if parts and hash_algorithm != manifest_part_business_hash(parts[0])[0]:
            raise AttachmentPlanError("ARCHIVE_MANIFEST_INVALID", "归档分卷哈希算法不一致。")
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
    return "、".join(values) + "检材内提取"


def _extraction_method(report: Mapping[str, Any], hash_algorithm: str) -> str:
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
    hashlib_name = next((
        key for key in runtime if key.casefold() in {"python hashlib", "hashmyfiles"}
    ), None)
    if not winrar or not hashlib_name:
        raise AttachmentPlanError("ATTACHMENT_PLAN_INVALID", "归档工具来源未确认。")
    attachments = report.get("attachments")
    snapshot = (
        _text(attachments.get("extraction_method"))
        if isinstance(attachments, Mapping) else ""
    )
    if snapshot:
        return snapshot
    hardware = _text(inspection.get("hardware_device")) or "取证设备"
    return hash_extraction_method(hardware, hash_algorithm)


def _part_row(item: Mapping[str, Any], manifest: Mapping[str, Any]) -> AttachmentPartRow:
    oversized_single = manifest.get("archive_mode") == "oversized_single_volume"
    return AttachmentPartRow(
        part_id=str(item["part_id"]), part_number=int(item["part_number"]),
        filename=str(item["filename"]), size_bytes=int(item["size_bytes"]),
        md5=manifest_part_business_hash(item)[1].upper(),
        disc_capacity_bytes=_capacity_value(
            item.get("disc_capacity_bytes"), optional=oversized_single,
        ),
        volume_size_bytes=_capacity_value(
            manifest.get("volume_size_bytes"), optional=oversized_single,
        ),
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


def _capacity_value(value: object, *, optional: bool) -> int | None:
    if optional and value is None:
        return None
    return _positive_int(value)

def _unsafe_filename(value: str) -> bool:
    return (PurePath(value).name != value or PureWindowsPath(value).name != value
            or value in {".", ".."} or "/" in value or "\\" in value)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()
