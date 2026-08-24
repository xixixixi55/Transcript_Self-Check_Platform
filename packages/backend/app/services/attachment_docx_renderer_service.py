"""Render stage-one attachment plans into the fixed template XML."""

from __future__ import annotations

import copy
from datetime import date
from typing import Any, Mapping, Sequence

from .attachment2_docx_renderer_service import render_attachment2
from .attachment2_image_service import Attachment2PhotoAsset
from .attachment_plan_models_service import (
    ARCHIVE_ROWS_PAGE_KIND,
    INSPECTOR_FINAL_PAGE_KIND,
    Attachment1PagePlan,
    AttachmentPlan,
)
from .docx_attachment_xml_service import (
    W_NS,
    allow_latin_character_wrap,
    attachment1_source_lines,
    clear_table_rows,
    clone_page_break,
    existing_vml_ids,
    make_unique_vml_ids,
    qn,
    replace_vml_text,
    set_paragraph_text,
    set_cell_text,
    set_cell_lines,
    set_element_font,
    set_paragraph_alignment,
    set_vertical_merge,
    text_of,
    trim_vml_line_vertical_span,
)
from .template_profile_service import (
    CurrentTemplateProfile,
    TemplateProfileError,
)
from .hash_algorithm_service import hash_display_name, hash_field_title

def render_attachment_plan(
    doc: Any, plan: AttachmentPlan, profile: CurrentTemplateProfile,
    report: Mapping[str, Any], photo_assets: Sequence[Attachment2PhotoAsset] = (),
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
    render_attachment2(doc, plan, profile, photo_assets)
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
        include_signature = (
            page.page_kind == INSPECTOR_FINAL_PAGE_KIND
            or (
                page_index == len(plan.attachment1_pages) - 1
                and page.page_kind == ARCHIVE_ROWS_PAGE_KIND
            )
        )
        nodes.append(_build_attachment1_table(
            original_table, template_rows, page, page_index == 0,
            include_signature, plan.hash_algorithm,
        ))
    for offset, node in enumerate(nodes):
        body.insert(start + offset, node)


def _build_attachment1_table(template: Any, rows: list[Any], page: Attachment1PagePlan,
                             include_header: bool, include_signature: bool,
                             hash_algorithm: str) -> Any:
    if page.page_kind not in {ARCHIVE_ROWS_PAGE_KIND, INSPECTOR_FINAL_PAGE_KIND}:
        raise TemplateProfileError("附件一页面类型不受 current-template-v1 支持。")
    if page.page_kind == INSPECTOR_FINAL_PAGE_KIND and page.serial_rows:
        raise TemplateProfileError("inspector final page cannot contain archive rows")
    table = copy.deepcopy(template)
    clear_table_rows(table)
    if include_header:
        header = copy.deepcopy(rows[0])
        header_cells = header.findall("./%s" % qn(W_NS, "tc"))
        if len(header_cells) >= 5:
            _set_attachment1_cell_text(
                header_cells[4], hash_field_title(hash_algorithm), 4,
            )
        table.append(header)
    data_template = rows[1]
    for index, item in enumerate(page.serial_rows):
        row = copy.deepcopy(data_template)
        cells = row.findall("./%s" % qn(W_NS, "tc"))
        values = [str(item.part_number), item.filename, page.source_text,
                  page.extraction_method, item.md5]
        for cell_index, (cell, value) in enumerate(zip(cells, values)):
            _set_attachment1_cell_text(cell, value, cell_index)
        if len(cells) >= 4:
            set_vertical_merge(cells[2], index == 0)
            set_vertical_merge(cells[3], index == 0)
            if index:
                _set_attachment1_cell_text(cells[2], "", 2)
                _set_attachment1_cell_text(cells[3], "", 3)
        table.append(row)
    if include_signature:
        blank_count = min(page.signature_blank_row_count, len(rows[2:-1]))
        blank_copies = [copy.deepcopy(row) for row in rows[2:2 + blank_count]]
        if blank_copies:
            trim_vml_line_vertical_span(blank_copies[0], blank_count, len(rows[2:-1]))
        table.extend(blank_copies)
        signature_row = copy.deepcopy(rows[-1])
        for cell in signature_row.findall("./%s" % qn(W_NS, "tc")):
            set_element_font(cell, "仿宋_GB2312", 32)
        table.append(signature_row)
    return table
def _set_attachment1_cell_text(cell: Any, value: str, cell_index: int) -> None:
    if cell_index == 2:
        set_cell_lines(cell, attachment1_source_lines(value))
        set_paragraph_alignment(cell, "both")
    else:
        set_cell_text(cell, value)
    if cell_index in (1, 4):
        allow_latin_character_wrap(cell)
    east_asia = "楷体" if cell_index == 0 else "仿宋_GB2312"
    size_half_points = 22 if cell_index == 3 else 32
    set_element_font(cell, east_asia, size_half_points)
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
        region_root = _region_root(region)
        replace_vml_text(
            region_root,
            {
                "inspection_place": place,
                "disc_number": page.disc_number,
                "md5_hash": page.md5,
                "burning_date": _format_date(page.burning_date),
            },
        )
        for paragraph in region_root.findall(".//%s" % qn(W_NS, "p")):
            if text_of(paragraph).startswith("文件哈希："):
                allow_latin_character_wrap(paragraph)
        selected_hash_name = hash_display_name(plan.hash_algorithm)
        if selected_hash_name != "MD5":
            for element in region:
                _replace_text_nodes(element, "MD5", selected_hash_name)
        if plan.archive_medium == "hard_drive":
            for element in region:
                _replace_text_nodes(element, "光盘编号：", "硬盘编号：")
                _replace_text_nodes(element, "刻录时间：", "拷贝时间：")
                _replace_text_nodes(element, "光盘粘贴处", "硬盘粘贴处")
        if end_anchor_element is not None:
            page_end_anchor = copy.deepcopy(end_anchor_element)
            _replace_element_text(page_end_anchor, first_disc, page.disc_number)
            if plan.archive_medium == "hard_drive":
                _replace_element_text(
                    page_end_anchor, "本鉴定中心刻制的", "本鉴定中心拷贝的",
                )
                _replace_element_text(page_end_anchor, "号光盘", "号硬盘")
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


def _replace_text_nodes(element: Any, old: str, new: str) -> None:
    """Replace a fixed label without flattening VML/textbox paragraph structure."""
    for node in element.findall(".//%s" % qn(W_NS, "t")):
        if node.text and old in node.text:
            node.text = node.text.replace(old, new)


def _format_date(value: str) -> str:
    year, month, day = value.split("-")
    return f"{date(int(year), int(month), int(day)).year}年{int(month)}月{int(day)}日"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()
