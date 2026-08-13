"""Small OOXML helpers used by the fixed attachment renderer."""

from __future__ import annotations

import copy
from typing import Any, Mapping

from lxml import etree

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
V_NS = "urn:schemas-microsoft-com:vml"

def qn(namespace: str, local: str) -> str:
    return "{%s}%s" % (namespace, local)


def text_of(element: Any) -> str:
    return "".join(node.text or "" for node in element.findall("./%s/%s" % (qn(W_NS, "r"), qn(W_NS, "t")))).strip()


def clear_text(element: Any) -> None:
    for node in element.findall(".//%s" % qn(W_NS, "t")):
        node.text = ""


def clone_page_break(anchor: Any) -> Any:
    page = copy.deepcopy(anchor)
    clear_text(page)
    return page


def set_cell_text(cell: Any, value: str) -> None:
    paragraphs = cell.findall(".//%s" % qn(W_NS, "p"))
    if not paragraphs:
        return
    text_nodes = paragraphs[0].findall(".//%s" % qn(W_NS, "t"))
    if not text_nodes:
        run = paragraphs[0].find("./%s" % qn(W_NS, "r"))
        if run is None:
            run = _new_run(paragraphs[0])
        existing = run.find("./%s" % qn(W_NS, "t"))
        text_nodes = [existing if existing is not None else _new_text(run)]
    text_nodes[0].text = value
    for node in text_nodes[1:]:
        node.text = ""
    for paragraph in paragraphs[1:]:
        clear_text(paragraph)


def set_element_font(element: Any, east_asia: str, size_half_points: int) -> None:
    """Apply an explicit East Asia font and size to all runs in an OOXML element."""
    for run in element.findall(".//%s" % qn(W_NS, "r")):
        r_pr = run.find("./%s" % qn(W_NS, "rPr"))
        if r_pr is None:
            r_pr = etree.Element(qn(W_NS, "rPr"))
            run.insert(0, r_pr)
        r_fonts = r_pr.find("./%s" % qn(W_NS, "rFonts"))
        if r_fonts is None:
            r_fonts = etree.Element(qn(W_NS, "rFonts"))
            r_pr.insert(0, r_fonts)
        for local in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
            r_fonts.attrib.pop(qn(W_NS, local), None)
        for local, value in (
            ("ascii", "Times New Roman"),
            ("hAnsi", "Times New Roman"),
            ("eastAsia", east_asia),
            ("cs", east_asia),
        ):
            r_fonts.set(qn(W_NS, local), value)
        for local in ("sz", "szCs"):
            size = r_pr.find("./%s" % qn(W_NS, local))
            if size is None:
                size = etree.SubElement(r_pr, qn(W_NS, local))
            size.set(qn(W_NS, "val"), str(size_half_points))


def set_paragraph_text(element: Any, value: str) -> None:
    nodes = element.findall(".//%s" % qn(W_NS, "t"))
    if not nodes:
        run = element.find("./%s" % qn(W_NS, "r"))
        if run is None:
            run = _new_run(element)
        nodes = [_new_text(run)]
    if nodes:
        nodes[0].text = value
        for node in nodes[1:]:
            node.text = ""


def set_cell_lines(cell: Any, lines: list[str]) -> None:
    paragraphs = cell.findall(".//%s" % qn(W_NS, "p"))
    if not paragraphs:
        return
    paragraph = paragraphs[0]
    runs = paragraph.findall("./%s" % qn(W_NS, "r"))
    run = runs[0] if runs else _new_run(paragraph)
    for extra in runs[1:]:
        paragraph.remove(extra)
    for child in list(run):
        if child.tag != qn(W_NS, "rPr"):
            run.remove(child)
    for index, line in enumerate(lines):
        if index:
            _new_child(run, W_NS, "br")
        node = _new_text(run)
        node.text = line
    for paragraph in paragraphs[1:]:
        clear_text(paragraph)


def set_vertical_merge(cell: Any, restart: bool) -> None:
    tc_pr = cell.find("./%s" % qn(W_NS, "tcPr"))
    if tc_pr is None:
        tc_pr = _new_child(cell, W_NS, "tcPr", before=True)
    merge = tc_pr.find("./%s" % qn(W_NS, "vMerge"))
    if merge is None:
        merge = _new_child(tc_pr, W_NS, "vMerge")
    if restart:
        merge.set(qn(W_NS, "val"), "restart")
    else:
        merge.attrib.pop(qn(W_NS, "val"), None)


def clear_table_rows(table: Any) -> None:
    for row in table.findall("./%s" % qn(W_NS, "tr")):
        table.remove(row)


def trim_vml_line_vertical_span(region: Any, retained_rows: int, template_rows: int) -> None:
    """Keep a copied blank-row diagonal inside the rows retained on the page."""
    if retained_rows <= 0 or template_rows <= 0:
        return
    ratio = min(retained_rows, template_rows) / template_rows
    for line in region.findall(".//%s" % qn(V_NS, "line")):
        start = line.get("from")
        end = line.get("to")
        if not start or not end or "," not in start or "," not in end:
            continue
        start_y = _vml_point_y(start)
        end_y = _vml_point_y(end)
        if start_y is None or end_y is None:
            continue
        line.set("to", _replace_vml_point_y(end, start_y + (end_y - start_y) * ratio))


def _vml_point_y(value: str) -> float | None:
    y_value = value.rsplit(",", 1)[-1].strip()
    unit = y_value[-2:] if y_value[-2:].isalpha() else ""
    try:
        return float(y_value.strip()[:-len(unit)] if unit else y_value.strip())
    except (IndexError, ValueError):
        return None


def _replace_vml_point_y(value: str, y_value: float) -> str:
    x_value, y_text = value.rsplit(",", 1)
    unit = y_text.strip()[-2:] if y_text.strip()[-2:].isalpha() else ""
    return "%s,%g%s" % (x_value, y_value, unit)


def replace_vml_text(region: Any, values: Mapping[str, str]) -> None:
    for textbox in region.findall(".//%s" % qn(V_NS, "textbox")):
        paragraphs = textbox.findall(".//%s" % qn(W_NS, "p"))
        if not paragraphs:
            continue
        template_lines = [text_of(paragraph) for paragraph in paragraphs]
        lines = []
        for template_line in template_lines:
            value = template_line
            for key, replacement in values.items():
                value = value.replace("{{%s}}" % key, replacement)
            if value:
                lines.append(value)
        for index, paragraph in enumerate(paragraphs):
            set_paragraph_text(paragraph, lines[index] if index < len(lines) else "")


def make_unique_vml_ids(region: Any, used_ids: set[str], suffix: str) -> None:
    for element in region.iter():
        if not str(element.tag).startswith("{%s}" % V_NS):
            continue
        value = element.get("id")
        if not value:
            continue
        candidate = value
        index = 1
        while candidate in used_ids:
            candidate = f"{value}_{suffix}_{index}"
            index += 1
        element.set("id", candidate)
        used_ids.add(candidate)


def existing_vml_ids(root: Any) -> set[str]:
    return {
        element.get("id") for element in root.iter()
        if str(element.tag).startswith("{%s}" % V_NS) and element.get("id")
    }


def _new_run(paragraph: Any) -> Any:
    return _new_child(paragraph, W_NS, "r")


def _new_text(run: Any) -> Any:
    return _new_child(run, W_NS, "t")


def _new_child(parent: Any, namespace: str, local: str, before: bool = False) -> Any:
    from lxml import etree
    element = etree.Element(qn(namespace, local))
    if before and len(parent):
        parent.insert(0, element)
    else:
        parent.append(element)
    return element
