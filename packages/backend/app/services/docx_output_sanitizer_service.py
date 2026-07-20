"""Remove template-only comments and metadata from generated DOCX copies."""

from __future__ import annotations

import os
import posixpath
import tempfile
import zipfile
from pathlib import Path

from lxml import etree

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_RPR_QN = f"{{{_W_NS}}}rPr"
_RUN_QN = f"{{{_W_NS}}}r"
_COLOR_QN = f"{{{_W_NS}}}color"
_COLOR_VALUE_QN = f"{{{_W_NS}}}val"
_CP_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
_DC_NS = "http://purl.org/dc/elements/1.1/"
_DCTERMS_NS = "http://purl.org/dc/terms/"
_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_REMOVED_PARTS = {
    "word/comments.xml",
    "word/commentsExtended.xml",
    "word/people.xml",
    "word/commentsIds.xml",
    "docProps/custom.xml",
}
_COMMENT_NAMES = {
    "commentRangeStart",
    "commentRangeEnd",
    "commentReference",
}
_RPR_CHILD_ORDER = {
    name: index
    for index, name in enumerate(
        (
            "rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps",
            "strike", "dStrike", "outline", "shadow", "emboss", "imprint",
            "noProof", "snapToGrid", "vanish", "webHidden", "color", "spacing",
            "w", "kern", "position", "sz", "szCs", "highlight", "u", "effect",
            "bdr", "shd", "fitText", "vertAlign", "rtl", "cs", "em", "lang",
            "eastAsianLayout", "specVanish", "oMath", "rPrChange",
        )
    )
}
_COLOR_ORDER = _RPR_CHILD_ORDER["color"]


def sanitize_generated_docx(path: str | Path) -> None:
    """Sanitize a saved output atomically, without changing the source template."""
    source = Path(path)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{source.stem}.", suffix=".sanitized.tmp", dir=source.parent
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(source, "r") as archive:
            parts = {
                info.filename: archive.read(info)
                for info in archive.infolist()
                if not info.is_dir() and info.filename not in _REMOVED_PARTS
            }
        parts = _sanitize_xml_parts(parts)
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in sorted(parts):
                archive.writestr(name, parts[name])
        os.replace(temporary, source)
    finally:
        temporary.unlink(missing_ok=True)


def _sanitize_xml_parts(parts: dict[str, bytes]) -> dict[str, bytes]:
    parsed: dict[str, etree._Element] = {}
    for name, content in parts.items():
        if name.endswith(".xml") or name.endswith(".rels"):
            parsed[name] = etree.fromstring(content)

    for name, root in parsed.items():
        if name.endswith(".xml"):
            if name.startswith("word/"):
                _normalize_font_colors(root)
            _remove_comment_markers(root)
            if name == "[Content_Types].xml":
                _remove_content_type_overrides(root)
            if name == "word/settings.xml":
                _remove_local_children(root, "docVars")
            if name == "docProps/core.xml":
                _sanitize_core_properties(root)
            if name == "docProps/app.xml":
                _sanitize_app_properties(root)
        if name.endswith(".rels"):
            _remove_relationships(name, root)

    for name in list(parts):
        if name in parsed:
            parts[name] = etree.tostring(parsed[name], encoding="UTF-8", xml_declaration=True)
    return parts


def _normalize_font_colors(root: etree._Element) -> None:
    """Make visible WordprocessingML run colors black in the output copy."""
    for rpr in root.iter(_RPR_QN):
        _set_black_color(rpr)
    for run in root.iter(_RUN_QN):
        if run.find(_RPR_QN) is None:
            rpr = etree.Element(_RPR_QN)
            run.insert(0, rpr)
            _set_black_color(rpr)


def _set_black_color(rpr: etree._Element) -> None:
    for child in list(rpr):
        if child.tag == _COLOR_QN:
            rpr.remove(child)

    color = etree.Element(_COLOR_QN)
    color.set(_COLOR_VALUE_QN, "000000")
    insert_at = len(rpr)
    for index, child in enumerate(rpr):
        child_order = _RPR_CHILD_ORDER.get(_local_name(child.tag), len(_RPR_CHILD_ORDER))
        if child_order > _COLOR_ORDER:
            insert_at = index
            break
    rpr.insert(insert_at, color)


def _remove_comment_markers(root: etree._Element) -> None:
    for parent in root.iter():
        for child in list(parent):
            if _local_name(child.tag) in _COMMENT_NAMES:
                parent.remove(child)


def _remove_local_children(root: etree._Element, local_name: str) -> None:
    for parent in root.iter():
        for child in list(parent):
            if _local_name(child.tag) == local_name:
                parent.remove(child)


def _remove_content_type_overrides(root: etree._Element) -> None:
    for child in list(root):
        if _local_name(child.tag) != "Override":
            continue
        part_name = child.get("PartName", "").lstrip("/")
        if part_name in _REMOVED_PARTS:
            root.remove(child)


def _remove_relationships(name: str, root: etree._Element) -> None:
    for relationship in list(root):
        if _local_name(relationship.tag) != "Relationship":
            continue
        target = relationship.get("Target", "")
        resolved = _resolve_relationship_target(name, target)
        rel_type = relationship.get("Type", "").casefold()
        remove_comment = (
            resolved in _REMOVED_PARTS
            or resolved.rsplit("/", 1)[-1].casefold() in {"comments.xml", "commentsextended.xml", "people.xml", "commentsids.xml"}
            or "comments" in rel_type
        )
        remove_custom = resolved == "docProps/custom.xml"
        if remove_comment or remove_custom:
            root.remove(relationship)


def _resolve_relationship_target(rels_name: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    if rels_name == "_rels/.rels":
        base = ""
    else:
        owner = rels_name.replace("/_rels/", "/", 1)
        owner = owner[:-5] if owner.endswith(".rels") else owner
        base = posixpath.dirname(owner)
    return posixpath.normpath(posixpath.join(base, target))


def _sanitize_core_properties(root: etree._Element) -> None:
    allowed = {"title", "creator", "lastModifiedBy", "revision"}
    for child in list(root):
        if _local_name(child.tag) not in allowed:
            root.remove(child)
    values = {
        "title": "",
        "creator": "文枢",
        "lastModifiedBy": "文枢",
        "revision": "1",
    }
    for local_name, value in values.items():
        node = next((child for child in root if _local_name(child.tag) == local_name), None)
        if node is None:
            namespace = _DC_NS if local_name == "title" else _CP_NS
            node = etree.SubElement(root, f"{{{namespace}}}{local_name}")
        node.text = value


def _sanitize_app_properties(root: etree._Element) -> None:
    for child in list(root):
        if _local_name(child.tag) in {"Company", "Manager", "HyperlinkBase", "Template"}:
            root.remove(child)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


__all__ = ["sanitize_generated_docx"]
