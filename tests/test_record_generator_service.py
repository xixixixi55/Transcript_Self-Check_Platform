"""SYNTHETIC T010 Word handoff regression coverage."""

import os
import sys
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))
sys.path.insert(0, os.path.dirname(__file__))

from app.services.record_generator_service import generate_docx  # noqa: E402
from app.services.template_filler_service import fill_template  # noqa: E402
from test_legacy_report_projection_service import _report  # noqa: E402


_ROOT = Path(__file__).parents[1]
_TEMPLATE = _ROOT / "word_templates" / "template.docx"


def test_generator_passes_the_same_saved_order_projection_to_word_renderer(tmp_path: Path):
    received = {}

    def fake_fill(report, _template, output, _photos):
        received["report"] = report
        Path(output).write_bytes(b"SYNTHETIC-DOCX")

    with patch("app.services.record_generator_service.fill_template", side_effect=fake_fill):
        generate_docx(_report(), output_dir=str(tmp_path))

    report = received["report"]
    assert [item["evidence_number"] for item in report["introduction"]["evidence_list"]] == ["SYNTHETIC-10", "SYNTHETIC-2"]
    assert [item["name"] for item in report["introduction"]["inspectors"]] == ["SYNTHETIC-B", "SYNTHETIC-A"]
    assert "SYNTHETIC-UI-COLOR" not in repr(report)
    assert "SYNTHETIC-UI-SOURCE" not in repr(report)


def test_template_docx_uses_saved_order_without_review_metadata(tmp_path: Path):
    output = tmp_path / "SYNTHETIC-ordered.docx"
    fill_template(_report(), str(_TEMPLATE), str(output))

    with zipfile.ZipFile(output) as package:
        document_xml = package.read("word/document.xml").decode("utf-8")

    assert document_xml.index("SYNTHETIC-10") < document_xml.index("SYNTHETIC-2")
    assert "SYNTHETIC-UI-COLOR" not in document_xml
    assert "SYNTHETIC-UI-SOURCE" not in document_xml
