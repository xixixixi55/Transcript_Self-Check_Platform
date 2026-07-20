"""Fixed current-template-v1 asset and semantic anchor checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .docx_package_service import (
    OOXML_PACKAGE_FINGERPRINT_ALGORITHM,
    DocxPackageError,
    compute_ooxml_package_fingerprint,
)

CURRENT_TEMPLATE_PROFILE_ID = "current-template-v1"
CURRENT_TEMPLATE_PACKAGE_FINGERPRINT = "616E3D1200C98DFD55C6DA7D5FB7DBB1C395BEF9FD78B1B6F59DC79BC4E814A7"
_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_V_NS = "urn:schemas-microsoft-com:vml"


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
    attachment3_label: str = "附件3："
    attachment3_end_anchor: str = "本鉴定中心刻制的"
    expected_attachment1_columns: int = 5
    expected_attachment1_header: tuple[str, ...] = (
        "序号", "电子数据", "来源", "提取方法", "文件MD5哈希值",
    )
    expected_attachment1_row_heights: tuple[int, ...] = (1392, 2024, 954, 954, 954, 2922)
    expected_page_height_twips: int = 16838
    expected_top_margin_twips: int = 1701
    expected_bottom_margin_twips: int = 1587
    expected_vml_textboxes: int = 2


def current_template_profile() -> CurrentTemplateProfile:
    return CurrentTemplateProfile(
        CURRENT_TEMPLATE_PROFILE_ID,
        OOXML_PACKAGE_FINGERPRINT_ALGORITHM,
        CURRENT_TEMPLATE_PACKAGE_FINGERPRINT,
    )


def validate_template_package_fingerprint(template_path: str) -> CurrentTemplateProfile:
    profile = current_template_profile()
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


def validate_current_template_profile(template_path: str, doc: Any) -> CurrentTemplateProfile:
    profile = validate_template_package_fingerprint(template_path)
    body = doc.element.body
    if _find_paragraph(body, profile.attachment1_label, exact=True) is None:
        raise TemplateProfileError("当前模板缺少附件一定位锚点。")
    if _find_paragraph(body, profile.attachment1_heading, exact=True) is None:
        raise TemplateProfileError("当前模板缺少附件一标题锚点。")
    if _find_paragraph(body, profile.attachment2_label, exact=True) is None:
        raise TemplateProfileError("当前模板缺少附件二定位锚点。")
    if _find_paragraph(body, profile.attachment3_label, exact=True) is None:
        raise TemplateProfileError("当前模板缺少附件三定位锚点。")
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
            or page_size.get("{%s}h" % _W_NS) != str(profile.expected_page_height_twips)
            or margins.get("{%s}top" % _W_NS) != str(profile.expected_top_margin_twips)
            or margins.get("{%s}bottom" % _W_NS) != str(profile.expected_bottom_margin_twips)):
        raise TemplateProfileError("当前模板页面尺寸或边距不匹配。")
    if len(body.findall(".//{%s}textbox" % _V_NS)) < profile.expected_vml_textboxes:
        raise TemplateProfileError("当前模板 VML 文本框数量不足。")
    if _find_paragraph(body, profile.attachment3_end_anchor) is None:
        raise TemplateProfileError("当前模板缺少附件三结束锚点。")
    return profile


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
