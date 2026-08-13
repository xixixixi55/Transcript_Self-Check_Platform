"""Synthetic structural tests for the versioned built-in template cleanup."""

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

from app.services.docx_package_service import (  # noqa: E402
    DocxPackageError,
    compute_ooxml_package_fingerprint,
    read_validated_docx_entries,
)
from app.services.template_profile_service import (  # noqa: E402
    CURRENT_TEMPLATE_PACKAGE_FINGERPRINT,
    LEGACY_TEMPLATE_PACKAGE_FINGERPRINT,
    validate_current_template_profile,
)

CURRENT = ROOT / "word_templates" / "template.docx"
LEGACY = ROOT / "word_templates" / "template-v1.0.0.docx"
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


def test_template_versions_have_stable_distinct_fingerprints():
    assert compute_ooxml_package_fingerprint(CURRENT) == CURRENT_TEMPLATE_PACKAGE_FINGERPRINT
    assert compute_ooxml_package_fingerprint(LEGACY) == LEGACY_TEMPLATE_PACKAGE_FINGERPRINT
    assert CURRENT_TEMPLATE_PACKAGE_FINGERPRINT != LEGACY_TEMPLATE_PACKAGE_FINGERPRINT


def test_cleanup_script_is_deterministic(tmp_path: Path):
    first = tmp_path / "SYNTHETIC-clean-1.docx"
    second = tmp_path / "SYNTHETIC-clean-2.docx"
    for output in (first, second):
        subprocess.run(
            [sys.executable, str(SCRIPT), str(LEGACY), str(output)],
            check=True, capture_output=True, text=True,
        )
    assert first.read_bytes() == second.read_bytes() == CURRENT.read_bytes()


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
