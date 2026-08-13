"""Center the current Word template without changing paragraph or table widths."""

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
FIXED_ZIP_TIMESTAMP = (2020, 1, 1, 0, 0, 0)


def balance_template_layout(source_path: str | Path, output_path: str | Path) -> None:
    """Balance direct body indents and center the fixed Attachment 1 table."""
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

    parts["word/document.xml"] = etree.tostring(
        root, encoding="UTF-8", xml_declaration=True,
    )
    _write_atomic(Path(output_path), parts)


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
