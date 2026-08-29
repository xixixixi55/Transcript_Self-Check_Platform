"""版本化内置模板清理的合成数据结构测试。"""

from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from docx import Document
from lxml import etree

ROOT = Path(__file__).parents[1]
sys.path.insert(0, os.path.join(ROOT, "packages", "backend"))

from app.services.document.docx_package_service import (  # noqa: E402
    DocxPackageError,
    compute_ooxml_package_fingerprint,
    read_validated_docx_entries,
)
from app.services.template.template_profile_service import (  # noqa: E402
    CURRENT_TEMPLATE_PACKAGE_FINGERPRINT,
    validate_current_template_profile,
)

CURRENT = ROOT / "word_templates" / "template.docx"
SCRIPT = ROOT / "scripts" / "clean_template_docx.py"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
V_NS = "urn:schemas-microsoft-com:vml"


def test_clean_template_has_no_comments_or_sample_media_and_keeps_anchors():
    with zipfile.ZipFile(CURRENT) as package:
        names = set(package.namelist())
        xml = {
            name: package.read(name)
            for name in names
            if name.endswith(".xml") or name.endswith(".rels")
        }
    combined = b"\n".join(xml.values()).lower()
    root = etree.fromstring(xml["word/document.xml"])
    body = root.find(f"{{{W_NS}}}body")
    paragraphs = body.findall(f"./{{{W_NS}}}p")
    texts = ["".join(paragraph.itertext()).strip() for paragraph in paragraphs]
    label_index = texts.index("附件2：")
    caption_index = texts.index("检材{{first_evidence_number}}照片")

    assert not any("comment" in name.casefold() for name in names)
    assert not any(name.startswith("word/media/") for name in names)
    assert b"commentrangestart" not in combined
    assert b"commentrangeend" not in combined
    assert b"commentreference" not in combined
    assert caption_index == label_index + 2
    assert texts[label_index + 1] == ""
    assert not paragraphs[label_index + 1].findall(f".//{{{V_NS}}}imagedata")
    validate_current_template_profile(str(CURRENT), Document(str(CURRENT)))


def test_current_template_has_stable_fingerprint_and_no_retired_assets():
    assert compute_ooxml_package_fingerprint(CURRENT) == CURRENT_TEMPLATE_PACKAGE_FINGERPRINT
    assert sorted(path.name for path in CURRENT.parent.glob("*.docx")) == ["template.docx"]


def test_privacy_cleanup_is_idempotent_and_removes_hidden_metadata(tmp_path: Path):
    first = tmp_path / "SYNTHETIC-private-clean-1.docx"
    second = tmp_path / "SYNTHETIC-private-clean-2.docx"
    for output in (first, second):
        subprocess.run(
            [sys.executable, str(SCRIPT), "--privacy-only", str(CURRENT), str(output)],
            check=True, capture_output=True, text=True,
        )
    assert first.read_bytes() == second.read_bytes() == CURRENT.read_bytes()
    with zipfile.ZipFile(first) as package:
        names = set(package.namelist())
        assert "docProps/custom.xml" not in names
        settings = etree.fromstring(package.read("word/settings.xml"))
        assert not settings.findall(f".//{{{W_NS}}}docVars")
        core = package.read("docProps/core.xml").decode("utf-8")
        assert "<dc:creator>文枢</dc:creator>" in core
        assert "<cp:lastModifiedBy>文枢</cp:lastModifiedBy>" in core


def test_current_template_has_balanced_body_and_centered_attachment_table():
    with zipfile.ZipFile(CURRENT) as package:
        root = etree.fromstring(package.read("word/document.xml"))
    body = root.find(f"{{{W_NS}}}body")
    section = body.find(f"{{{W_NS}}}sectPr")
    margins = section.find(f"{{{W_NS}}}pgMar")
    assert margins.get(f"{{{W_NS}}}left") == margins.get(f"{{{W_NS}}}right") == "1587"

    horizontal_indents = []
    for paragraph in body.findall(f"./{{{W_NS}}}p"):
        indent = paragraph.find(f"./{{{W_NS}}}pPr/{{{W_NS}}}ind")
        if indent is None or not any(
            indent.get(f"{{{W_NS}}}{name}") is not None
            for name in ("left", "right", "leftChars", "rightChars")
        ):
            continue
        horizontal_indents.append(indent)
    assert len(horizontal_indents) == 62
    assert all(
        abs(
            int(indent.get(f"{{{W_NS}}}left", "0"))
            - int(indent.get(f"{{{W_NS}}}right", "0"))
        ) <= 1
        for indent in horizontal_indents
    )
    assert all(
        indent.get(f"{{{W_NS}}}leftChars") is None
        and indent.get(f"{{{W_NS}}}rightChars") is None
        for indent in horizontal_indents
    )

    table_properties = body.find(f"./{{{W_NS}}}tbl/{{{W_NS}}}tblPr")
    assert table_properties.find(f"{{{W_NS}}}tblInd") is None
    assert table_properties.find(f"{{{W_NS}}}jc").get(f"{{{W_NS}}}val") == "center"

    assert len(body.findall(f".//{{{W_NS}}}br[@{{{W_NS}}}type='page']")) > 0
    assert len(body.findall(f".//{{{V_NS}}}textbox")) >= 2


def test_current_template_centers_title_headings_and_horizontal_rules():
    with zipfile.ZipFile(CURRENT) as package:
        parts = {name: package.read(name) for name in package.namelist()}
    root = etree.fromstring(parts["word/document.xml"])
    body = root.find(f"{{{W_NS}}}body")
    paragraphs = {
        "".join(paragraph.itertext()).strip(): paragraph
        for paragraph in body.findall(f"./{{{W_NS}}}p")
    }
    title = body.find(f"./{{{W_NS}}}p")
    title_properties = title.find(f"{{{W_NS}}}pPr")
    assert title_properties.find(f"{{{W_NS}}}jc").get(f"{{{W_NS}}}val") == "center"
    assert title_properties.find(f"{{{W_NS}}}tabs") is None
    assert not title.findall(f".//{{{W_NS}}}tab")

    reference = paragraphs["（一）检查方法"].find(
        f"./{{{W_NS}}}pPr/{{{W_NS}}}ind",
    )
    reference_left = int(reference.get(f"{{{W_NS}}}left"))
    for text in ("一、绪论", "二、检查"):
        indent = paragraphs[text].find(f"./{{{W_NS}}}pPr/{{{W_NS}}}ind")
        assert int(indent.get(f"{{{W_NS}}}left")) < reference_left
        assert all(
            indent.get(f"{{{W_NS}}}{name}") is None
            for name in ("firstLine", "firstLineChars", "hanging", "hangingChars")
        )
    for text in ("（三）检查过程", "（四）检查结果"):
        indent = paragraphs[text].find(f"./{{{W_NS}}}pPr/{{{W_NS}}}ind")
        assert indent.get(f"{{{W_NS}}}left") == reference.get(f"{{{W_NS}}}left")
        assert indent.get(f"{{{W_NS}}}right") == reference.get(f"{{{W_NS}}}right")
        assert all(
            indent.get(f"{{{W_NS}}}{name}") is None
            for name in ("firstLine", "firstLineChars", "hanging", "hangingChars")
        )

    page_width_points = 11906 / 20
    margin_points = 1587 / 20
    for part_name in ("word/document.xml", "word/footer1.xml", "word/footer2.xml"):
        part = etree.fromstring(parts[part_name])
        rules = [
            line for line in part.findall(f".//{{{V_NS}}}line")
            if line.get("strokeweight") == "4.5pt"
            and _coordinate(line.get("from"), 1) == _coordinate(line.get("to"), 1)
        ]
        assert len(rules) == 1
        start = _coordinate(rules[0].get("from"), 0)
        end = _coordinate(rules[0].get("to"), 0)
        assert margin_points + (start + end) / 2 == pytest.approx(
            page_width_points / 2, abs=0.01,
        )


def _coordinate(value: str, index: int) -> float:
    return float(value.split(",")[index].removesuffix("pt"))


def test_cleanup_script_rejects_unsafe_or_duplicate_entries(tmp_path: Path):
    for index, entries in enumerate((
        [("word/document.xml", b"one"), ("word/document.xml", b"two")],
        [("word/../document.xml", b"unsafe")],
        [("/word/document.xml", b"unsafe")],
    )):
        source = tmp_path / f"SYNTHETIC-unsafe-{index}.docx"
        with zipfile.ZipFile(source, "w") as package:
            for name, content in entries:
                package.writestr(name, content)
        with pytest.raises(DocxPackageError):
            read_validated_docx_entries(source)
