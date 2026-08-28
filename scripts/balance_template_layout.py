"""在不改变内容宽度或分页的前提下，将当前 Word 模板居中。"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import zipfile
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "backend"))

from app.services.docx_package_service import read_validated_docx_entries  # noqa: E402

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = f"{{{W_NS}}}"
V_NS = "urn:schemas-microsoft-com:vml"
V = f"{{{V_NS}}}"
FIXED_ZIP_TIMESTAMP = (2020, 1, 1, 0, 0, 0)
TOP_LEVEL_HEADINGS = {"一、绪论", "二、检查"}
SECOND_LEVEL_HEADINGS = {"（三）检查过程", "（四）检查结果"}
SECOND_LEVEL_REFERENCE = "（一）检查方法"
HORIZONTAL_RULE_PARTS = (
    "word/document.xml",
    "word/footer1.xml",
    "word/footer2.xml",
)


def balance_template_layout(source_path: str | Path, output_path: str | Path) -> None:
    """平衡正文的直接缩进，并将固定的附件 1 表格居中。"""
    parts = dict(read_validated_docx_entries(Path(source_path)))
    root = etree.fromstring(parts["word/document.xml"])
    body = root.find(f"{W}body")
    if body is None:
        raise ValueError("template document body is missing")

    section = body.find(f"{W}sectPr")
    page_size = None if section is None else section.find(f"{W}pgSz")
    margins = None if section is None else section.find(f"{W}pgMar")
    if page_size is None or margins is None:
        raise ValueError("template page geometry is missing")
    if margins.get(f"{W}left") != margins.get(f"{W}right"):
        raise ValueError("template page margins must already be symmetric")

    balanced_count = 0
    for paragraph in body.findall(f"./{W}p"):
        indent = paragraph.find(f"./{W}pPr/{W}ind")
        if indent is None:
            continue
        horizontal_attributes = (
            indent.get(f"{W}left"), indent.get(f"{W}right"),
            indent.get(f"{W}leftChars"), indent.get(f"{W}rightChars"),
        )
        if all(value is None for value in horizontal_attributes):
            continue
        if indent.get(f"{W}left") is None and indent.get(f"{W}right") is None:
            raise ValueError("character-only body indents cannot be balanced safely")
        left = int(indent.get(f"{W}left", "0"))
        right = int(indent.get(f"{W}right", "0"))
        balanced_left = (left + right) // 2
        balanced_right = left + right - balanced_left
        indent.set(f"{W}left", str(balanced_left))
        indent.set(f"{W}right", str(balanced_right))
        indent.attrib.pop(f"{W}leftChars", None)
        indent.attrib.pop(f"{W}rightChars", None)
        balanced_count += 1
    if balanced_count == 0:
        raise ValueError("template has no offset body paragraphs to balance")

    tables = body.findall(f"./{W}tbl")
    if len(tables) != 1:
        raise ValueError("template must contain exactly one direct Attachment 1 table")
    table_properties = tables[0].find(f"{W}tblPr")
    if table_properties is None:
        raise ValueError("Attachment 1 table properties are missing")
    table_indent = table_properties.find(f"{W}tblInd")
    if table_indent is not None:
        table_properties.remove(table_indent)
    alignment = table_properties.find(f"{W}jc")
    if alignment is None:
        alignment = etree.Element(f"{W}jc")
        table_width = table_properties.find(f"{W}tblW")
        insertion_index = (
            len(table_properties)
            if table_width is None
            else table_properties.index(table_width) + 1
        )
        table_properties.insert(insertion_index, alignment)
        alignment.set(f"{W}val", "center")

    _center_visible_title(body)
    _align_structural_headings(body)
    _center_horizontal_rules(
        parts,
        root,
        int(page_size.get(f"{W}w")),
        int(margins.get(f"{W}left")),
    )

    parts["word/document.xml"] = etree.tostring(
        root, encoding="UTF-8", xml_declaration=True,
    )
    _write_atomic(Path(output_path), parts)


def _center_visible_title(body: etree._Element) -> None:
    paragraphs = body.findall(f"./{W}p")
    if not paragraphs:
        raise ValueError("template title paragraph is missing")
    title = paragraphs[0]
    properties = title.find(f"{W}pPr")
    if properties is None:
        raise ValueError("template title properties are missing")
    tabs = properties.find(f"{W}tabs")
    if tabs is not None:
        properties.remove(tabs)
    alignment = properties.find(f"{W}jc")
    if alignment is None:
        alignment = etree.SubElement(properties, f"{W}jc")
    alignment.set(f"{W}val", "center")
    visible_tabs = title.findall(f".//{W}tab")
    if len(visible_tabs) != 2:
        raise ValueError("template title tab anchors do not match the fixed profile")
    for tab in visible_tabs:
        tab.getparent().remove(tab)


def _align_structural_headings(body: etree._Element) -> None:
    by_text = {
        _paragraph_text(paragraph): paragraph
        for paragraph in body.findall(f"./{W}p")
    }
    missing = (TOP_LEVEL_HEADINGS | SECOND_LEVEL_HEADINGS | {SECOND_LEVEL_REFERENCE}) - set(by_text)
    if missing:
        raise ValueError(f"template structural headings are missing: {sorted(missing)}")

    reference_indent = _required_indent(by_text[SECOND_LEVEL_REFERENCE])
    reference_left = reference_indent.get(f"{W}left")
    reference_right = reference_indent.get(f"{W}right")
    if reference_left is None or reference_right is None:
        raise ValueError("second-level heading reference is missing fixed boundaries")

    for text in TOP_LEVEL_HEADINGS:
        indent = _required_indent(by_text[text])
        _clear_first_line_indent(indent)
        if int(indent.get(f"{W}left", "0")) >= int(reference_left):
            raise ValueError("top-level headings must protrude beyond second-level headings")

    for text in SECOND_LEVEL_HEADINGS:
        indent = _required_indent(by_text[text])
        indent.set(f"{W}left", reference_left)
        indent.set(f"{W}right", reference_right)
        _clear_first_line_indent(indent)


def _required_indent(paragraph: etree._Element) -> etree._Element:
    indent = paragraph.find(f"./{W}pPr/{W}ind")
    if indent is None:
        raise ValueError(f"template heading indent is missing: {_paragraph_text(paragraph)}")
    return indent


def _clear_first_line_indent(indent: etree._Element) -> None:
    for name in ("firstLine", "firstLineChars", "hanging", "hangingChars"):
        indent.attrib.pop(f"{W}{name}", None)


def _paragraph_text(paragraph: etree._Element) -> str:
    return "".join(paragraph.itertext()).strip()


def _center_horizontal_rules(
    parts: dict[str, bytes],
    document_root: etree._Element,
    page_width_twips: int,
    left_margin_twips: int,
) -> None:
    page_width_points = page_width_twips / 20
    left_margin_points = left_margin_twips / 20
    for part_name in HORIZONTAL_RULE_PARTS:
        if part_name not in parts:
            raise ValueError(f"template horizontal-rule part is missing: {part_name}")
        root = (
            document_root
            if part_name == "word/document.xml"
            else etree.fromstring(parts[part_name])
        )
        rules = []
        for line in root.findall(f".//{V}line"):
            start_x, start_y = _point_pair(line.get("from"))
            end_x, end_y = _point_pair(line.get("to"))
            if abs(start_y - end_y) <= 0.01 and line.get("strokeweight") == "4.5pt":
                rules.append((line, start_x, start_y, end_x, end_y))
        if len(rules) != 1:
            raise ValueError(
                f"template horizontal-rule count does not match in {part_name}",
            )
        line, start_x, start_y, end_x, end_y = rules[0]
        length = end_x - start_x
        centered_start = (page_width_points - length) / 2 - left_margin_points
        centered_end = centered_start + length
        line.set("from", f"{_point(centered_start)}pt,{_point(start_y)}pt")
        line.set("to", f"{_point(centered_end)}pt,{_point(end_y)}pt")
        if part_name != "word/document.xml":
            parts[part_name] = etree.tostring(
                root, encoding="UTF-8", xml_declaration=True,
            )


def _point_pair(value: str | None) -> tuple[float, float]:
    if not value or "," not in value:
        raise ValueError("template VML line coordinates are invalid")
    x, y = value.split(",", 1)
    return _point_value(x), _point_value(y)


def _point_value(value: str) -> float:
    normalized = value.strip()
    if normalized.endswith("pt"):
        normalized = normalized[:-2]
    try:
        return float(normalized)
    except ValueError as error:
        raise ValueError("template VML line coordinate is invalid") from error


def _point(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _write_atomic(output: Path, parts: dict[str, bytes]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(
        prefix=f".{output.stem}.", suffix=".docx.tmp", dir=output.parent,
    )
    os.close(handle)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as package:
            for name in sorted(parts):
                info = zipfile.ZipInfo(name, FIXED_ZIP_TIMESTAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o600 << 16
                package.writestr(info, parts[name])
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    balance_template_layout(args.source, args.output)


if __name__ == "__main__":
    main()
