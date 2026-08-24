"""Fixed current-template-v1 asset and semantic anchor checks."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..repository.template_approval_repository import TemplateApprovalRepository
from ..repository.template_registry_repository import TemplateRegistryRepository
from ..repository.workbench_database import utc_now
from ..repository.workbench_errors import WorkbenchPersistenceError
from .docx_package_service import (
    OOXML_PACKAGE_FINGERPRINT_ALGORITHM,
    DocxPackageError,
    compute_ooxml_package_fingerprint,
)
from .template_layout_validation_service import has_refined_visible_layout
from .attachment2_image_service import (
    ATTACHMENT2_GROUP_GAP_TWIPS,
    ATTACHMENT2_PAGE_BREAK_AFTER_TWIPS,
    ATTACHMENT2_SLOT_HEIGHT_EMU,
    ATTACHMENT2_SLOT_ROW_HEIGHT_TWIPS,
    ATTACHMENT2_SLOT_WIDTH_EMU,
)

CURRENT_TEMPLATE_PROFILE_ID = "current-template-v1"
BUILTIN_TEMPLATE_ID = "electronic-inspection-record"
CURRENT_TEMPLATE_VERSION = "1.0.4"
CURRENT_TEMPLATE_PACKAGE_FINGERPRINT = "F253C5AE3F61CE55A08DF3E46D3BE9640053C004B152C9AE712A2999C88236A5"
PREVIOUS_TEMPLATE_VERSION = "1.0.2"
PREVIOUS_TEMPLATE_PACKAGE_FINGERPRINT = "B61C12CC2A1144E9FA33B2A221E4EF778D9625C2AFAF04AF3B38024B13794B32"
CLEAN_TEMPLATE_VERSION = "1.0.1"
CLEAN_TEMPLATE_PACKAGE_FINGERPRINT = "206AC62CC093D587E1BB59E9286427570C637BF3B9041814BF2DCFD652DB8232"
LEGACY_TEMPLATE_VERSION = "1.0.0"
LEGACY_TEMPLATE_PACKAGE_FINGERPRINT = "616E3D1200C98DFD55C6DA7D5FB7DBB1C395BEF9FD78B1B6F59DC79BC4E814A7"
RETIRED_BUILTIN_TEMPLATE_VERSIONS = frozenset({"1.0.0", "1.0.1", "1.0.2", "1.0.3"})
CURRENT_TEMPLATE_VALIDATION_RULE = {
    "rule_id": "current-template-profile",
    "version": "1.0.0",
}
_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_V_NS = "urn:schemas-microsoft-com:vml"


def is_historical_builtin_template_ref(template_ref: Any) -> bool:
    """Return whether a reference is the read-only built-in export asset."""
    return isinstance(template_ref, Mapping) and (
        template_ref.get("template_id") == BUILTIN_TEMPLATE_ID
        and template_ref.get("version") in RETIRED_BUILTIN_TEMPLATE_VERSIONS
    )


class TemplateProfileError(ValueError):
    """Raised when the fixed template is missing or has drifted."""

    def __init__(self, message: str, code: str = "TEMPLATE_PROFILE_MISMATCH"):
        super().__init__(message)
        self.code = code
        self.safe_message = message

@dataclass(frozen=True)
class CurrentTemplateProfile:
    profile_id: str
    fingerprint_algorithm: str
    package_fingerprint: str
    raw_template_sha256: str | None = None
    attachment1_label: str = "附件1："
    attachment1_heading: str = "电子数据提取固定清单"
    attachment2_label: str = "附件2："
    attachment2_caption_anchor: str = "检材{{first_evidence_number}}照片"
    attachment2_slot_width_emu: int = ATTACHMENT2_SLOT_WIDTH_EMU
    attachment2_slot_height_emu: int = ATTACHMENT2_SLOT_HEIGHT_EMU
    attachment2_slot_row_height_twips: int = ATTACHMENT2_SLOT_ROW_HEIGHT_TWIPS
    attachment2_page_break_after_twips: int = ATTACHMENT2_PAGE_BREAK_AFTER_TWIPS
    attachment2_group_gap_twips: int = ATTACHMENT2_GROUP_GAP_TWIPS
    attachment2_slot_count: int = 2
    attachment2_slot_columns: int = 2
    attachment2_two_image_table_columns: int = 2
    attachment2_four_image_table_columns: int = 2
    attachment2_pair_size: int = 2
    attachment2_max_images_per_page: int = 4
    attachment3_label: str = "附件3："
    attachment3_end_anchor: str = "本鉴定中心刻制的"
    expected_attachment1_columns: int = 5
    expected_attachment1_header: tuple[str, ...] = (
        "序号", "电子数据", "来源", "提取方法", "文件MD5哈希值",
    )
    expected_attachment1_row_heights: tuple[int, ...] = (1392, 2024, 954, 954, 954, 2922)
    expected_page_height_twips: int = 16838
    expected_page_width_twips: int = 11906
    expected_top_margin_twips: int = 1701
    expected_bottom_margin_twips: int = 1587
    expected_horizontal_margin_twips: int = 1587
    expected_vml_textboxes: int = 2


def current_template_profile(package_fingerprint: str = CURRENT_TEMPLATE_PACKAGE_FINGERPRINT) -> CurrentTemplateProfile:
    return CurrentTemplateProfile(
        CURRENT_TEMPLATE_PROFILE_ID,
        OOXML_PACKAGE_FINGERPRINT_ALGORITHM,
        package_fingerprint,
    )


def validate_template_package_fingerprint(template_path: str, expected_fingerprint: str = CURRENT_TEMPLATE_PACKAGE_FINGERPRINT) -> CurrentTemplateProfile:
    profile = current_template_profile(expected_fingerprint)
    path = Path(template_path)
    if not path.is_file():
        raise TemplateProfileError("当前模板资产不存在或已漂移。")
    try:
        package_fingerprint = compute_ooxml_package_fingerprint(path)
    except DocxPackageError as error:
        raise TemplateProfileError(error.args[0], error.code) from error
    if package_fingerprint != profile.package_fingerprint:
        raise TemplateProfileError("当前模板资产不存在或已漂移。")
    return profile


def validate_current_template_profile(
    template_path: str, doc: Any,
    expected_fingerprint: str = CURRENT_TEMPLATE_PACKAGE_FINGERPRINT,
    template_ref: Any = None,
) -> CurrentTemplateProfile:
    profile = validate_template_package_fingerprint(template_path, expected_fingerprint)
    body = doc.element.body
    direct_paragraphs = body.findall("./{%s}p" % _W_NS)
    if len(direct_paragraphs) < 2 or not paragraph_text(direct_paragraphs[0]).strip():
        raise TemplateProfileError("当前模板缺少固定标题槽。")
    if "{{document_number}}" not in paragraph_text(direct_paragraphs[1]):
        raise TemplateProfileError("当前模板文号槽位置不匹配。")
    if _find_paragraph(body, profile.attachment1_label, exact=True) is None:
        raise TemplateProfileError("当前模板缺少附件一定位锚点。")
    if _find_paragraph(body, profile.attachment1_heading, exact=True) is None:
        raise TemplateProfileError("当前模板缺少附件一标题锚点。")
    label2 = _find_paragraph(body, profile.attachment2_label, exact=True)
    label3 = _find_paragraph(body, profile.attachment3_label, exact=True)
    caption2 = _find_paragraph(body, profile.attachment2_caption_anchor, exact=True)
    if label2 is None:
        raise TemplateProfileError("当前模板缺少附件二定位锚点。")
    if caption2 is None:
        raise TemplateProfileError("当前模板缺少附件二图片说明锚点。")
    if label3 is None:
        raise TemplateProfileError("当前模板缺少附件三定位锚点。")
    children = list(body)
    label2_index, caption2_index = children.index(label2), children.index(caption2)
    if caption2_index <= label2_index or not _is_attachment2_region(children[label2_index + 1:caption2_index]):
        raise TemplateProfileError("当前模板附件二图片区域结构不匹配。")
    if _page_break_count(label2) != 1 or _page_break_count(label3) != 1:
        raise TemplateProfileError("当前模板附件章节分页锚点不匹配。")
    tables = body.findall(".//{%s}tbl" % _W_NS)
    if len(tables) != 1:
        raise TemplateProfileError("当前模板附件一表格数量不匹配。")
    table = tables[0]
    rows = table.findall("./{%s}tr" % _W_NS)
    headers = tuple(paragraph_text(cell) for cell in rows[0].findall("./{%s}tc" % _W_NS)) if rows else ()
    if (len(rows) != len(profile.expected_attachment1_row_heights)
            or len(headers) != profile.expected_attachment1_columns
            or headers != profile.expected_attachment1_header):
        raise TemplateProfileError("当前模板附件一表格结构不匹配。")
    for row, expected_height in zip(rows, profile.expected_attachment1_row_heights):
        height = row.find("./{%s}trPr/{%s}trHeight" % (_W_NS, _W_NS))
        if height is None or height.get("{%s}val" % _W_NS) != str(expected_height):
            raise TemplateProfileError("当前模板附件一行高结构不匹配。")
    if "检查人员" not in paragraph_text(rows[-1].find("./{%s}tc" % _W_NS)):
        raise TemplateProfileError("当前模板缺少检查人员区域锚点。")
    section = body.find("./{%s}sectPr" % _W_NS)
    page_size = None if section is None else section.find("./{%s}pgSz" % _W_NS)
    margins = None if section is None else section.find("./{%s}pgMar" % _W_NS)
    if (page_size is None or margins is None
            or page_size.get("{%s}w" % _W_NS) != str(profile.expected_page_width_twips)
            or page_size.get("{%s}h" % _W_NS) != str(profile.expected_page_height_twips)
            or margins.get("{%s}top" % _W_NS) != str(profile.expected_top_margin_twips)
            or margins.get("{%s}bottom" % _W_NS) != str(profile.expected_bottom_margin_twips)
            or margins.get("{%s}left" % _W_NS) != str(profile.expected_horizontal_margin_twips)
            or margins.get("{%s}right" % _W_NS) != str(profile.expected_horizontal_margin_twips)):
        raise TemplateProfileError("当前模板页面尺寸或边距不匹配。")
    if not _has_balanced_horizontal_layout(body, table):
        raise TemplateProfileError("当前模板正文或附件一未居中。")
    if not has_refined_visible_layout(
        template_path,
        body,
        profile.expected_page_width_twips,
        profile.expected_horizontal_margin_twips,
    ):
        raise TemplateProfileError("当前模板标题、层级或横线未居中。")
    if len(body.findall(".//{%s}textbox" % _V_NS)) < profile.expected_vml_textboxes:
        raise TemplateProfileError("当前模板 VML 文本框数量不足。")
    if _find_paragraph(body, profile.attachment3_end_anchor) is None:
        raise TemplateProfileError("当前模板缺少附件三结束锚点。")
    return profile


def _has_balanced_horizontal_layout(body: Any, table: Any) -> bool:
    balanced_paragraph_count = 0
    for paragraph in body.findall("./{%s}p" % _W_NS):
        indent = paragraph.find("./{%s}pPr/{%s}ind" % (_W_NS, _W_NS))
        if indent is None:
            continue
        horizontal_attributes = (
            indent.get("{%s}left" % _W_NS),
            indent.get("{%s}right" % _W_NS),
            indent.get("{%s}leftChars" % _W_NS),
            indent.get("{%s}rightChars" % _W_NS),
        )
        if all(value is None for value in horizontal_attributes):
            continue
        balanced_paragraph_count += 1
        left = int(indent.get("{%s}left" % _W_NS, "0"))
        right = int(indent.get("{%s}right" % _W_NS, "0"))
        if abs(left - right) > 1:
            return False
        if indent.get("{%s}leftChars" % _W_NS) is not None:
            return False
        if indent.get("{%s}rightChars" % _W_NS) is not None:
            return False
    properties = table.find("./{%s}tblPr" % _W_NS)
    alignment = None if properties is None else properties.find("./{%s}jc" % _W_NS)
    table_indent = None if properties is None else properties.find("./{%s}tblInd" % _W_NS)
    return (
        balanced_paragraph_count > 0
        and alignment is not None
        and alignment.get("{%s}val" % _W_NS) == "center"
        and table_indent is None
    )


def require_registered_template(
    registry: TemplateRegistryRepository,
    approvals: TemplateApprovalRepository,
    template_ref: Any,
) -> dict[str, Any]:
    """Resolve an approved version and revalidate its immutable asset and profile."""
    try:
        template = registry.get_internal(template_ref)
        approvals.require_approved(template_ref)
    except WorkbenchPersistenceError as error:
        code = error.code if error.code in {"TEMPLATE_UNKNOWN", "TEMPLATE_NOT_APPROVED"} else "TEMPLATE_UNKNOWN"
        raise TemplateProfileError(_safe_template_summary(code), code) from error
    path = Path(template["internal_locator"])
    if not path.is_file():
        code = "TEMPLATE_ASSET_MISSING"
        raise TemplateProfileError(_safe_template_summary(code), code)
    if template["validation_rules"] != [CURRENT_TEMPLATE_VALIDATION_RULE]:
        code = "TEMPLATE_RULE_VALIDATION_FAILED"
        raise TemplateProfileError(_safe_template_summary(code), code)
    try:
        actual = compute_ooxml_package_fingerprint(path)
    except DocxPackageError as error:
        code = "TEMPLATE_RULE_VALIDATION_FAILED"
        raise TemplateProfileError(_safe_template_summary(code), code) from error
    if actual != template["fingerprint"]:
        code = "TEMPLATE_FINGERPRINT_MISMATCH"
        raise TemplateProfileError(_safe_template_summary(code), code)
    try:
        from docx import Document
        validate_current_template_profile(
            str(path), Document(str(path)), template["fingerprint"],
            template["template_ref"],
        )
    except (OSError, ValueError, TemplateProfileError) as error:
        code = "TEMPLATE_RULE_VALIDATION_FAILED"
        raise TemplateProfileError(_safe_template_summary(code), code) from error
    return template


def validate_registered_template(
    registry: TemplateRegistryRepository,
    approvals: TemplateApprovalRepository,
    template_ref: Any,
) -> dict[str, Any]:
    try:
        template = require_registered_template(registry, approvals, template_ref)
    except TemplateProfileError as error:
        return {"valid": False, "error_code": error.code, "safe_summary": error.safe_message}
    approval = approvals.require_approved(template_ref)
    return {
        "valid": True,
        "template": registry.public_with_approval(template_ref, approval),
        "validated_at": utc_now(),
    }


def _safe_template_summary(code: str) -> str:
    return {
        "TEMPLATE_UNKNOWN": "所选模板版本不存在。",
        "TEMPLATE_NOT_APPROVED": "所选模板版本未通过审核。",
        "TEMPLATE_ASSET_MISSING": "所选模板资产不可用。",
        "TEMPLATE_FINGERPRINT_MISMATCH": "所选模板指纹校验失败。",
        "TEMPLATE_RULE_VALIDATION_FAILED": "所选模板结构校验失败。",
    }[code]


def body_children(doc: Any) -> list[Any]:
    return list(doc.element.body)


def paragraph_text(element: Any) -> str:
    return "".join(node.text or "" for node in element.findall(".//{%s}t" % _W_NS)).strip()


def _find_paragraph(body: Any, anchor: str, exact: bool = False) -> Any | None:
    for element in body.findall("./{%s}p" % _W_NS):
        value = paragraph_text(element)
        if (value == anchor if exact else anchor in value):
            return element
    return None


def _is_attachment2_region(elements: list[Any]) -> bool:
    if not elements:
        return False
    return all(
        element.tag == "{%s}p" % _W_NS and not paragraph_text(element)
        for element in elements
    )


def _page_break_count(element: Any) -> int:
    return sum(
        node.get("{%s}type" % _W_NS) == "page"
        for node in element.findall(".//{%s}br" % _W_NS)
    )
