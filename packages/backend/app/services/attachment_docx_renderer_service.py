"""Render stage-one attachment plans into the fixed template XML."""

from __future__ import annotations

import copy
from datetime import date
from typing import Any, Mapping

from .attachment_plan_models_service import Attachment1PagePlan, AttachmentPlan
from .docx_attachment_xml_service import (
    W_NS,
    clear_table_rows,
    clone_page_break,
    existing_vml_ids,
    make_unique_vml_ids,
    qn,
    replace_vml_text,
    set_paragraph_text,
    set_cell_text,
    set_vertical_merge,
    text_of,
)
from .template_profile_service import (
    CurrentTemplateProfile,
    TemplateProfileError,
)


def render_attachment_plan(
    doc: Any, plan: AttachmentPlan, profile: CurrentTemplateProfile,
    report: Mapping[str, Any],
) -> None:
    """Replace only the attachment regions described by current-template-v1."""
    body = doc.element.body
    label1 = _find_paragraph(body, profile.attachment1_label)
    heading1 = _find_paragraph(body, profile.attachment1_heading, exact=True)
    label3 = _find_paragraph(body, profile.attachment3_label)
    table = _table_after(body, heading1)
    if label1 is None or heading1 is None or label3 is None or table is None:
        raise TemplateProfileError("当前模板附件锚点在渲染前丢失。")
    _render_attachment1(body, label1, heading1, table, plan, report)
    if plan.attachment2_state.photo_count == 0:
        label2 = _find_paragraph(body, profile.attachment2_label, exact=True)
        if label2 is not None:
            previous = label2.getprevious()
            if previous is not None and _is_empty_boundary_paragraph(previous):
                body.remove(previous)
            body.remove(label2)
        label3_after_skip = _find_paragraph(body, profile.attachment3_label)
        while label3_after_skip is not None:
            previous = label3_after_skip.getprevious()
            if previous is None or not _is_empty_boundary_paragraph(previous):
                break
            body.remove(previous)
    label3 = _find_paragraph(body, profile.attachment3_label)
    if label3 is None:
        raise TemplateProfileError("当前模板附件三锚点在渲染前丢失。")
    _render_attachment3(body, label3, plan, report, profile.attachment3_end_anchor)


def _render_attachment1(body: Any, label: Any, heading: Any, table: Any,
                        plan: AttachmentPlan, report: Mapping[str, Any]) -> None:
    children = body_children_from(body)
    start = children.index(label)
    original_table = copy.deepcopy(table)
    template_rows = original_table.findall("./%s" % qn(W_NS, "tr"))
    if len(template_rows) < 2:
        raise TemplateProfileError("当前模板附件一缺少数据行模板。")
    page_break_anchor = copy.deepcopy(label)
    for element in (label, heading, table):
        body.remove(element)
    nodes = []
    for page_index, page in enumerate(plan.attachment1_pages):
        nodes.append(label if page_index == 0 else clone_page_break(page_break_anchor))
        if page_index == 0:
            nodes.append(heading)
        nodes.append(_build_attachment1_table(
            original_table, template_rows, page, page_index == 0,
            page_index == len(plan.attachment1_pages) - 1,
        ))
    for offset, node in enumerate(nodes):
        body.insert(start + offset, node)


def _build_attachment1_table(template: Any, rows: list[Any], page: Attachment1PagePlan,
                             include_header: bool, include_signature: bool) -> Any:
    if page.page_kind != "archive_rows":
        raise TemplateProfileError("附件一页面类型不受 current-template-v1 支持。")
    table = copy.deepcopy(template)
    clear_table_rows(table)
    if include_header:
        table.append(copy.deepcopy(rows[0]))
    data_template = rows[1]
    for index, item in enumerate(page.serial_rows):
        row = copy.deepcopy(data_template)
        cells = row.findall("./%s" % qn(W_NS, "tc"))
        values = [str(item.part_number), item.filename, page.source_text,
                  page.extraction_method, item.md5]
        for cell, value in zip(cells, values):
            set_cell_text(cell, value)
        if len(cells) >= 4:
            set_vertical_merge(cells[2], index == 0)
            set_vertical_merge(cells[3], index == 0)
            if index:
                set_cell_text(cells[2], "")
                set_cell_text(cells[3], "")
        table.append(row)
    if include_signature:
        for blank_row in rows[2:-1]:
            table.append(copy.deepcopy(blank_row))
        table.append(copy.deepcopy(rows[-1]))
    return table


def _render_attachment3(body: Any, label: Any, plan: AttachmentPlan,
                        report: Mapping[str, Any], end_anchor: str) -> None:
    children = body_children_from(body)
    start = children.index(label)
    end = next((index for index in range(start, len(children))
                if children[index].tag == qn(W_NS, "sectPr")), len(children))
    source_region = [copy.deepcopy(element) for element in children[start:end]]
    end_index = next(
        (index for index, element in enumerate(source_region)
         if element.tag == qn(W_NS, "p") and end_anchor in text_of(element)),
        None,
    )
    end_anchor_element = None if end_index is None else copy.deepcopy(source_region[end_index])
    tail = [] if end_index is None else source_region[end_index + 1:]
    if end_index is not None:
        source_region = source_region[:end_index]
    page_break_anchor = copy.deepcopy(source_region[0])
    _remove_page_breaks(source_region[0])
    for element in children[start:end]:
        body.remove(element)
    used_ids = existing_vml_ids(body)
    place = _text((report.get("introduction") or {}).get("inspection_place"))
    nodes = []
    first_disc = plan.attachment3_pages[0].disc_number
    for index, page in enumerate(plan.attachment3_pages, 1):
        region = [copy.deepcopy(element) for element in source_region]
        if index == 1:
            region[0] = copy.deepcopy(page_break_anchor)
        else:
            nodes.append(clone_page_break(page_break_anchor))
        if not page.show_attachment_title:
            region = region[1:]
        replace_vml_text(
            _region_root(region),
            {
                "inspection_place": place,
                "disc_number": page.disc_number,
                "md5_hash": page.md5,
                "burning_date": _format_date(page.burning_date),
            },
            filename=page.filename,
        )
        if end_anchor_element is not None:
            page_end_anchor = copy.deepcopy(end_anchor_element)
            _replace_element_text(page_end_anchor, first_disc, page.disc_number)
            region.append(page_end_anchor)
        for element in region:
            make_unique_vml_ids(element, used_ids, f"attachment3_{index}")
            nodes.append(element)
    nodes.extend(tail)
    for offset, node in enumerate(nodes):
        body.insert(start + offset, node)


def _region_root(nodes: list[Any]) -> Any:
    from lxml import etree
    root = etree.Element("attachment-region")
    for node in nodes:
        root.append(node)
    return root


def body_children_from(body: Any) -> list[Any]:
    return list(body)


def _find_paragraph(body: Any, anchor: str, exact: bool = False) -> Any | None:
    for element in body.findall("./%s" % qn(W_NS, "p")):
        value = text_of(element)
        if (value == anchor if exact else anchor in value):
            return element
    return None


def _table_after(body: Any, anchor: Any) -> Any | None:
    if anchor is None:
        return None
    children = body_children_from(body)
    index = children.index(anchor)
    return next((element for element in children[index + 1:]
                 if element.tag == qn(W_NS, "tbl")), None)


def _clear_first_text(element: Any) -> None:
    from .docx_attachment_xml_service import set_paragraph_text
    set_paragraph_text(element, "")


def _remove_page_breaks(element: Any) -> None:
    for node in list(element.findall(".//%s" % qn(W_NS, "br"))):
        if node.get(qn(W_NS, "type")) == "page":
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)


def _is_empty_boundary_paragraph(element: Any) -> bool:
    """Identify empty boundary paragraphs left when Attachment2 is skipped."""
    if element.tag != qn(W_NS, "p") or text_of(element):
        return False
    return not any(
        element.findall(".//%s" % qn(W_NS, local))
        for local in ("drawing", "pict", "object", "fldChar")
    )


def _replace_element_text(element: Any, old: str, new: str) -> None:
    nodes = element.findall(".//%s" % qn(W_NS, "t"))
    if not nodes:
        return
    full = "".join(node.text or "" for node in nodes).replace(old, new)
    set_paragraph_text(element, full)


def _format_date(value: str) -> str:
    year, month, day = value.split("-")
    return f"{date(int(year), int(month), int(day)).year}年{int(month)}月{int(day)}日"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()
