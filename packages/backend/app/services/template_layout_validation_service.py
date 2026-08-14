"""Visible Word-layout checks that supplement structural DOCX validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lxml import etree

from .docx_package_service import DocxPackageError, read_validated_docx_entries

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
V_NS = "urn:schemas-microsoft-com:vml"
TOP_LEVEL_HEADINGS = {"一、绪论", "二、检查"}
SECOND_LEVEL_HEADINGS = {"（三）检查过程", "（四）检查结果"}
SECOND_LEVEL_REFERENCE = "（一）检查方法"
HORIZONTAL_RULE_PARTS = (
    "word/document.xml",
    "word/footer1.xml",
    "word/footer2.xml",
)


def has_refined_visible_layout(
    template_path: str,
    body: Any,
    page_width_twips: int,
    horizontal_margin_twips: int,
) -> bool:
    """Return whether title, heading hierarchy, and fixed rules are centered."""
    return (
        _has_centered_visible_title(body)
        and _has_structural_heading_hierarchy(body)
        and _has_centered_horizontal_rules(
            template_path,
            page_width_twips,
            horizontal_margin_twips,
        )
    )


def _has_centered_visible_title(body: Any) -> bool:
    title = body.find(f"./{{{W_NS}}}p")
    if title is None:
        return False
    alignment = title.find(f"./{{{W_NS}}}pPr/{{{W_NS}}}jc")
    return (
        alignment is not None
        and alignment.get(f"{{{W_NS}}}val") == "center"
        and title.find(f"./{{{W_NS}}}pPr/{{{W_NS}}}tabs") is None
        and not title.findall(f".//{{{W_NS}}}tab")
    )


def _has_structural_heading_hierarchy(body: Any) -> bool:
    paragraphs = {
        _paragraph_text(paragraph): paragraph
        for paragraph in body.findall(f"./{{{W_NS}}}p")
    }
    required = TOP_LEVEL_HEADINGS | SECOND_LEVEL_HEADINGS | {
        SECOND_LEVEL_REFERENCE,
    }
    if not required.issubset(paragraphs):
        return False
    reference = _paragraph_indent(paragraphs[SECOND_LEVEL_REFERENCE])
    if reference is None:
        return False
    reference_left = reference.get(f"{{{W_NS}}}left")
    reference_right = reference.get(f"{{{W_NS}}}right")
    if reference_left is None or reference_right is None:
        return False
    for text in TOP_LEVEL_HEADINGS:
        indent = _paragraph_indent(paragraphs[text])
        if (
            indent is None
            or _has_first_line_indent(indent)
            or int(indent.get(f"{{{W_NS}}}left", "0")) >= int(reference_left)
        ):
            return False
    for text in SECOND_LEVEL_HEADINGS:
        indent = _paragraph_indent(paragraphs[text])
        if (
            indent is None
            or _has_first_line_indent(indent)
            or indent.get(f"{{{W_NS}}}left") != reference_left
            or indent.get(f"{{{W_NS}}}right") != reference_right
        ):
            return False
    return True


def _paragraph_text(paragraph: Any) -> str:
    return "".join(paragraph.xpath(".//w:t/text()")).strip()


def _paragraph_indent(paragraph: Any) -> Any:
    return paragraph.find(f"./{{{W_NS}}}pPr/{{{W_NS}}}ind")


def _has_first_line_indent(indent: Any) -> bool:
    return any(
        indent.get(f"{{{W_NS}}}{name}") is not None
        for name in ("firstLine", "firstLineChars", "hanging", "hangingChars")
    )


def _has_centered_horizontal_rules(
    template_path: str,
    page_width_twips: int,
    horizontal_margin_twips: int,
) -> bool:
    try:
        parts = dict(read_validated_docx_entries(Path(template_path)))
    except DocxPackageError:
        return False
    page_width_points = page_width_twips / 20
    left_margin_points = horizontal_margin_twips / 20
    for part_name in HORIZONTAL_RULE_PARTS:
        raw = parts.get(part_name)
        if raw is None:
            return False
        try:
            root = etree.fromstring(raw)
        except etree.XMLSyntaxError:
            return False
        rules = []
        for line in root.findall(f".//{{{V_NS}}}line"):
            try:
                start_x, start_y = _point_pair(line.get("from"))
                end_x, end_y = _point_pair(line.get("to"))
            except ValueError:
                return False
            if abs(start_y - end_y) <= 0.01 and line.get("strokeweight") == "4.5pt":
                rules.append((start_x, end_x))
        if len(rules) != 1:
            return False
        start_x, end_x = rules[0]
        length = end_x - start_x
        expected_start = (page_width_points - length) / 2 - left_margin_points
        if abs(start_x - expected_start) > 0.01:
            return False
    return True


def _point_pair(value: str | None) -> tuple[float, float]:
    if not value or "," not in value:
        raise ValueError("invalid VML coordinates")
    x, y = value.split(",", 1)
    return _point_value(x), _point_value(y)


def _point_value(value: str) -> float:
    normalized = value.strip()
    if normalized.endswith("pt"):
        normalized = normalized[:-2]
    return float(normalized)
