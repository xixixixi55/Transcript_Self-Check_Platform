"""以确定性方式从 DOCX 中删除批注和附件 2 示例图片。"""

from __future__ import annotations

import argparse
import os
import posixpath
import sys
import tempfile
import zipfile
from pathlib import Path

from lxml import etree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "backend"))

from app.services.document.docx_package_service import read_validated_docx_entries  # noqa: E402

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
V_NS = "urn:schemas-microsoft-com:vml"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
COMMENT_PARTS = {
    "word/comments.xml",
    "word/commentsExtended.xml",
    "word/commentsIds.xml",
    "word/people.xml",
}
COMMENT_MARKERS = {"commentRangeStart", "commentRangeEnd", "commentReference"}
FIXED_ZIP_TIMESTAMP = (2020, 1, 1, 0, 0, 0)
CP_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC_NS = "http://purl.org/dc/elements/1.1/"
PRIVACY_REMOVED_PARTS = {"docProps/custom.xml"}


def clean_template(source_path: str | Path, output_path: str | Path) -> None:
    """在保留空的附件 2 锚点段落的同时，写入已清理的模板。"""
    source = Path(source_path)
    output = Path(output_path)
    parts = {
        name: content
        for name, content in read_validated_docx_entries(source)
        if name not in COMMENT_PARTS
    }

    removed_relationship_ids = _clean_document(parts)
    _remove_comment_markers(parts)
    removed_media = _remove_document_relationships(parts, removed_relationship_ids)
    for name in removed_media:
        parts.pop(name, None)
    _remove_comment_content_types(parts)
    _write_atomic(output, parts)


def sanitize_template_privacy(source_path: str | Path, output_path: str | Path) -> None:
    """保留可见 OOXML 字节，同时删除不参与渲染的身份元数据。"""
    source = Path(source_path)
    output = Path(output_path)
    parts = {
        name: content
        for name, content in read_validated_docx_entries(source)
        if name not in PRIVACY_REMOVED_PARTS
    }
    _sanitize_core_properties(parts)
    _remove_docvars(parts)
    _remove_custom_property_relationship(parts)
    _remove_custom_property_content_type(parts)
    _write_atomic(output, parts)


def _sanitize_core_properties(parts: dict[str, bytes]) -> None:
    name = "docProps/core.xml"
    root = etree.fromstring(parts[name])
    for child in list(root):
        root.remove(child)
    values = (
        (DC_NS, "title", ""),
        (DC_NS, "creator", "文枢"),
        (CP_NS, "lastModifiedBy", "文枢"),
        (CP_NS, "revision", "1"),
    )
    for namespace, local_name, value in values:
        node = etree.SubElement(root, f"{{{namespace}}}{local_name}")
        node.text = value
    parts[name] = _xml_bytes(root)


def _remove_docvars(parts: dict[str, bytes]) -> None:
    name = "word/settings.xml"
    root = etree.fromstring(parts[name])
    for child in list(root):
        if _local_name(child.tag) == "docVars":
            root.remove(child)
    parts[name] = _xml_bytes(root)


def _remove_custom_property_relationship(parts: dict[str, bytes]) -> None:
    name = "_rels/.rels"
    root = etree.fromstring(parts[name])
    for relationship in list(root):
        if (
            relationship.get("Target", "").lstrip("/") in PRIVACY_REMOVED_PARTS
            or "custom-properties" in relationship.get("Type", "").casefold()
        ):
            root.remove(relationship)
    parts[name] = _xml_bytes(root)


def _remove_custom_property_content_type(parts: dict[str, bytes]) -> None:
    name = "[Content_Types].xml"
    root = etree.fromstring(parts[name])
    for child in list(root):
        if child.get("PartName", "").lstrip("/") in PRIVACY_REMOVED_PARTS:
            root.remove(child)
    parts[name] = _xml_bytes(root)


def _clean_document(parts: dict[str, bytes]) -> set[str]:
    root = etree.fromstring(parts["word/document.xml"])
    body = root.find(f"{{{W_NS}}}body")
    if body is None:
        raise ValueError("template document body is missing")
    label = _direct_paragraph(body, "附件2：")
    caption = _direct_paragraph(body, "检材{{first_evidence_number}}照片")
    if label is None or caption is None:
        raise ValueError("Attachment 2 anchors are missing")
    children = list(body)
    start, end = children.index(label) + 1, children.index(caption)
    if start >= end:
        raise ValueError("Attachment 2 sample image region is missing")

    relationship_ids: set[str] = set()
    for element in children[start:end]:
        for image_data in element.findall(f".//{{{V_NS}}}imagedata"):
            relationship_id = image_data.get(f"{{{R_NS}}}id")
            if relationship_id:
                relationship_ids.add(relationship_id)
        for child in list(element):
            if child.tag != f"{{{W_NS}}}pPr":
                element.remove(child)
    if not relationship_ids:
        raise ValueError("Attachment 2 sample images are missing")
    parts["word/document.xml"] = _xml_bytes(root)
    return relationship_ids


def _remove_comment_markers(parts: dict[str, bytes]) -> None:
    for name, content in list(parts.items()):
        if not name.endswith(".xml"):
            continue
        root = etree.fromstring(content)
        changed = False
        for parent in root.iter():
            for child in list(parent):
                if _local_name(child.tag) in COMMENT_MARKERS:
                    parent.remove(child)
                    changed = True
        if changed:
            parts[name] = _xml_bytes(root)


def _remove_document_relationships(
    parts: dict[str, bytes], image_relationship_ids: set[str],
) -> set[str]:
    name = "word/_rels/document.xml.rels"
    root = etree.fromstring(parts[name])
    removed_media: set[str] = set()
    for relationship in list(root):
        relationship_id = relationship.get("Id", "")
        relationship_type = relationship.get("Type", "").casefold()
        target = relationship.get("Target", "")
        resolved = _resolve_target("word/document.xml", target)
        if (
            "comments" in relationship_type
            or resolved in COMMENT_PARTS
            or relationship_id in image_relationship_ids
        ):
            if relationship_id in image_relationship_ids:
                removed_media.add(resolved)
            root.remove(relationship)
    parts[name] = _xml_bytes(root)
    return removed_media


def _remove_comment_content_types(parts: dict[str, bytes]) -> None:
    name = "[Content_Types].xml"
    root = etree.fromstring(parts[name])
    for child in list(root):
        part_name = child.get("PartName", "").lstrip("/")
        content_type = child.get("ContentType", "").casefold()
        if part_name in COMMENT_PARTS or "comments" in content_type:
            root.remove(child)
    parts[name] = _xml_bytes(root)


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


def _direct_paragraph(body: etree._Element, expected: str) -> etree._Element | None:
    for paragraph in body.findall(f"./{{{W_NS}}}p"):
        text = "".join(paragraph.itertext()).strip()
        if text == expected:
            return paragraph
    return None


def _resolve_target(owner_name: str, target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(owner_name), target))


def _xml_bytes(root: etree._Element) -> bytes:
    return etree.tostring(root, encoding="UTF-8", xml_declaration=True)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--preserve-source-as", type=Path)
    parser.add_argument("--privacy-only", action="store_true")
    args = parser.parse_args()
    if args.preserve_source_as:
        args.preserve_source_as.write_bytes(args.source.read_bytes())
        source = args.preserve_source_as
    else:
        source = args.source
    if args.privacy_only:
        sanitize_template_privacy(source, args.output)
    else:
        clean_template(source, args.output)


if __name__ == "__main__":
    main()
