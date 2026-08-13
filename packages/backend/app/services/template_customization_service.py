"""Layer 21: deterministic, allow-listed patching of a validated DOCX."""

from __future__ import annotations

import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Mapping

from lxml import etree

from ..repository.workbench_errors import WorkbenchPersistenceError
from .docx_package_service import read_validated_docx_entries

ALLOWED_BODY_FONTS = ("仿宋_GB2312", "仿宋", "宋体")
ALLOWED_BODY_FONT_SIZES = (14, 15, 16, 17, 18)
_DOCUMENT_XML = "word/document.xml"
_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_NS = {"w": _W_NS}
_PROTECTED_HEADINGS = {"一、绪论", "二、检查", "电子数据提取固定清单"}


def customize_template(
    source_path: str | Path,
    destination_path: str | Path,
    customization: Mapping[str, Any],
) -> None:
    value = _validate_customization(customization)
    entries = dict(read_validated_docx_entries(source_path))
    document_xml = entries.get(_DOCUMENT_XML)
    if document_xml is None:
        raise WorkbenchPersistenceError("TEMPLATE_RULE_VALIDATION_FAILED")
    entries[_DOCUMENT_XML] = _patch_document_xml(document_xml, value)
    _write_package(source_path, destination_path, entries)


def read_template_customization(source_path: str | Path) -> dict[str, Any]:
    entries = dict(read_validated_docx_entries(source_path))
    document_xml = entries.get(_DOCUMENT_XML)
    if document_xml is None:
        raise WorkbenchPersistenceError("TEMPLATE_RULE_VALIDATION_FAILED")
    root = _parse_document(document_xml)
    paragraphs = _direct_body_paragraphs(root)
    title = _paragraph_text(_fixed_title_paragraph(paragraphs)).replace(
        "{{title}}", "电子数据检查笔录",
    ).strip()
    font, size = _first_body_typography(paragraphs)
    return {
        "document_title": title,
        "body_font": font if font in ALLOWED_BODY_FONTS else "仿宋_GB2312",
        "body_font_size": size if size in ALLOWED_BODY_FONT_SIZES else 16,
    }


def _validate_customization(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "document_title", "body_font", "body_font_size",
    }:
        raise WorkbenchPersistenceError("TEMPLATE_CUSTOMIZATION_INVALID")
    title, font, size = (
        value.get("document_title"), value.get("body_font"), value.get("body_font_size"),
    )
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 40:
        raise WorkbenchPersistenceError("TEMPLATE_CUSTOMIZATION_INVALID")
    if any(character in title for character in "{}\r\n\t"):
        raise WorkbenchPersistenceError("TEMPLATE_CUSTOMIZATION_INVALID")
    if font not in ALLOWED_BODY_FONTS or size not in ALLOWED_BODY_FONT_SIZES:
        raise WorkbenchPersistenceError("TEMPLATE_CUSTOMIZATION_INVALID")
    return {"document_title": title.strip(), "body_font": font, "body_font_size": size}


def _patch_document_xml(document_xml: bytes, value: Mapping[str, Any]) -> bytes:
    root = _parse_document(document_xml)
    paragraphs = _direct_body_paragraphs(root)
    title = _fixed_title_paragraph(paragraphs)
    title_nodes = title.xpath(".//w:t", namespaces=_NS)
    content_nodes = [node for node in title_nodes if (node.text or "").strip()]
    if not content_nodes:
        raise WorkbenchPersistenceError("TEMPLATE_RULE_VALIDATION_FAILED")
    content_nodes[0].text = str(value["document_title"])
    for node in content_nodes[1:]:
        node.text = ""
    for paragraph in _body_paragraphs(paragraphs):
        for run in paragraph.xpath("./w:r", namespaces=_NS):
            _set_run_typography(run, str(value["body_font"]), int(value["body_font_size"]))
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _parse_document(value: bytes) -> Any:
    try:
        return etree.fromstring(value, parser=etree.XMLParser(resolve_entities=False))
    except etree.XMLSyntaxError as error:
        raise WorkbenchPersistenceError("TEMPLATE_RULE_VALIDATION_FAILED") from error


def _direct_body_paragraphs(root: Any) -> list[Any]:
    return list(root.xpath("/w:document/w:body/w:p", namespaces=_NS))


def _fixed_title_paragraph(paragraphs: list[Any]) -> Any:
    if (
        len(paragraphs) < 2
        or not _paragraph_text(paragraphs[0]).strip()
        or "{{document_number}}" not in _paragraph_text(paragraphs[1])
    ):
        raise WorkbenchPersistenceError("TEMPLATE_RULE_VALIDATION_FAILED")
    return paragraphs[0]


def _body_paragraphs(paragraphs: list[Any]) -> list[Any]:
    result = []
    for paragraph in paragraphs[2:]:
        text = "".join(_paragraph_text(paragraph).split())
        if text.startswith("附件："):
            break
        if text not in _PROTECTED_HEADINGS:
            result.append(paragraph)
    return result


def _paragraph_text(paragraph: Any) -> str:
    return "".join(paragraph.xpath(".//w:t/text()", namespaces=_NS))


def _set_run_typography(run: Any, font: str, size: int) -> None:
    properties = run.find(f"{{{_W_NS}}}rPr")
    if properties is None:
        properties = etree.Element(f"{{{_W_NS}}}rPr")
        run.insert(0, properties)
    fonts = properties.find(f"{{{_W_NS}}}rFonts")
    if fonts is None:
        fonts = etree.SubElement(properties, f"{{{_W_NS}}}rFonts")
    for attribute in ("ascii", "hAnsi", "eastAsia", "cs"):
        fonts.set(f"{{{_W_NS}}}{attribute}", font)
    half_points = str(size * 2)
    for name in ("sz", "szCs"):
        node = properties.find(f"{{{_W_NS}}}{name}")
        if node is None:
            node = etree.SubElement(properties, f"{{{_W_NS}}}{name}")
        node.set(f"{{{_W_NS}}}val", half_points)


def _first_body_typography(paragraphs: list[Any]) -> tuple[str | None, int | None]:
    for paragraph in _body_paragraphs(paragraphs):
        for run in paragraph.xpath("./w:r", namespaces=_NS):
            properties = run.find(f"{{{_W_NS}}}rPr")
            if properties is None:
                continue
            fonts = properties.find(f"{{{_W_NS}}}rFonts")
            size = properties.find(f"{{{_W_NS}}}sz")
            font = None if fonts is None else fonts.get(f"{{{_W_NS}}}eastAsia")
            points = None if size is None else int(size.get(f"{{{_W_NS}}}val")) // 2
            if font in ALLOWED_BODY_FONTS and points in ALLOWED_BODY_FONT_SIZES:
                return font, points
    return None, None


def _write_package(
    source_path: str | Path, destination_path: str | Path, entries: Mapping[str, bytes],
) -> None:
    destination = Path(destination_path)
    fd, staged_name = tempfile.mkstemp(
        prefix=".template-customization-", suffix=".docx", dir=destination.parent,
    )
    os.close(fd)
    staged = Path(staged_name)
    try:
        with zipfile.ZipFile(source_path, "r") as source, zipfile.ZipFile(staged, "w") as output:
            for info in source.infolist():
                if info.is_dir():
                    output.writestr(info, b"")
                else:
                    output.writestr(info, entries[info.filename])
        os.replace(staged, destination)
    except Exception:
        staged.unlink(missing_ok=True)
        raise


__all__ = [
    "ALLOWED_BODY_FONTS", "ALLOWED_BODY_FONT_SIZES", "customize_template",
    "read_template_customization",
]
