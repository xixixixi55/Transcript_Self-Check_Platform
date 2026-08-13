"""SYNTHETIC T010 Word handoff regression coverage."""

import os
import sys
import zipfile
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))
sys.path.insert(0, os.path.dirname(__file__))

from app.services.record_generator_service import generate_docx  # noqa: E402
from app.repository.template_approval_repository import TemplateApprovalRepository  # noqa: E402
from app.repository.template_registry_repository import TemplateRegistryRepository  # noqa: E402
from app.repository.workbench_database import WorkbenchDatabase  # noqa: E402
from app.services.docx_package_service import compute_ooxml_package_fingerprint  # noqa: E402
from app.services.template_profile_service import (  # noqa: E402
    CURRENT_TEMPLATE_PACKAGE_FINGERPRINT,
    CURRENT_TEMPLATE_VALIDATION_RULE,
    TemplateProfileError,
)
from app.services.template_filler_service import fill_template  # noqa: E402
from test_legacy_report_projection_service import _report  # noqa: E402
from test_template_filler_service import _manifest  # noqa: E402


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


def test_generator_uses_user_output_filename_when_provided(tmp_path: Path):
    def fake_fill(report, _template, output, _photos):
        Path(output).write_bytes(b"SYNTHETIC-DOCX")

    with patch("app.services.record_generator_service.fill_template", side_effect=fake_fill):
        generated = generate_docx(_report(), output_dir=str(tmp_path), output_filename="用户命名.docx")
    assert Path(generated).name == "用户命名.docx"

    # Path separators and Windows-invalid characters are stripped; .docx ensured.
    with patch("app.services.record_generator_service.fill_template", side_effect=fake_fill):
        generated = generate_docx(_report(), output_dir=str(tmp_path), output_filename=r"C:\SYNTHETIC\bad:name")
    assert Path(generated).name == "badname.docx"

    with patch("app.services.record_generator_service.fill_template", side_effect=fake_fill):
        generated = generate_docx(_report(), output_dir=str(tmp_path), output_filename="no-extension")
    assert Path(generated).name == "no-extension.docx"


def test_template_docx_uses_saved_order_without_review_metadata(tmp_path: Path):
    output = tmp_path / "SYNTHETIC-ordered.docx"
    fill_template(_report(), str(_TEMPLATE), str(output))

    with zipfile.ZipFile(output) as package:
        document_xml = package.read("word/document.xml").decode("utf-8")

    assert document_xml.index("SYNTHETIC-10") < document_xml.index("SYNTHETIC-2")
    assert "SYNTHETIC-UI-COLOR" not in document_xml
    assert "SYNTHETIC-UI-SOURCE" not in document_xml


def _registered_template(tmp_path: Path, status="approved", template=_TEMPLATE):
    database = WorkbenchDatabase(tmp_path / "SYNTHETIC-workbench.sqlite3", "SYNTHETIC-GENERATOR")
    template = Path(template)
    registry = TemplateRegistryRepository(database, (template.parent,))
    approvals = TemplateApprovalRepository(database, registry)
    reference = {"template_id": "template-SYNTHETIC-generator", "version": "1.0.0"}
    registry.register({
        "schema_version": 1, "template_ref": reference,
        "display_name": "SYNTHETIC generator template",
        "fingerprint": compute_ooxml_package_fingerprint(template),
        "validation_rules": [CURRENT_TEMPLATE_VALIDATION_RULE],
        "asset_id": "asset-SYNTHETIC-generator",
        "registered_at": "2026-07-30T00:00:00+00:00",
    }, template)
    approvals.record(reference, {
        "approval_record_id": "approval-SYNTHETIC-generator",
        "status": status, "acceptance_summary": "SYNTHETIC acceptance",
        "recorded_at": "2026-07-30T01:00:00+00:00",
    })
    return registry, approvals, reference


def test_generator_uses_revalidated_case_template_without_archive_side_effect(tmp_path: Path):
    registry, approvals, reference = _registered_template(tmp_path)
    output = tmp_path / "exports" / "SYNTHETIC-selected.docx"
    archive_rows_before = database_rows(registry.database, "archive_attempts")

    def fake_fill(
        _report, selected_path, generated_path, _photos,
        *, expected_template_fingerprint, template_ref,
    ):
        assert Path(selected_path) == _TEMPLATE.resolve()
        assert expected_template_fingerprint == CURRENT_TEMPLATE_PACKAGE_FINGERPRINT
        assert template_ref == reference
        Path(generated_path).write_bytes(b"SYNTHETIC-DOCX")

    with patch("app.services.record_generator_service.fill_template", side_effect=fake_fill):
        generated = generate_docx(
            _report(), output_dir=str(output.parent), template_ref=reference,
            template_registry=registry, template_approvals=approvals,
        )

    assert Path(generated).read_bytes() == b"SYNTHETIC-DOCX"
    assert database_rows(registry.database, "archive_attempts") == archive_rows_before
    assert database_rows(registry.database, "archive_plans") == []


def test_generator_rejects_unapproved_case_template_without_fallback(tmp_path: Path):
    registry, approvals, reference = _registered_template(tmp_path, status="pending")
    with patch("app.services.record_generator_service.fill_template") as fill:
        with pytest.raises(TemplateProfileError) as error:
            generate_docx(
                _report(), output_dir=str(tmp_path / "exports"), template_ref=reference,
                template_registry=registry, template_approvals=approvals,
            )
    assert error.value.code == "TEMPLATE_NOT_APPROVED"
    assert fill.call_count == 0


def test_formal_generator_reuses_registered_fingerprint_for_all_word_gates(tmp_path: Path):
    template = tmp_path / "SYNTHETIC-version-2.docx"
    with zipfile.ZipFile(_TEMPLATE) as source, zipfile.ZipFile(
        template, "w", compression=zipfile.ZIP_DEFLATED,
    ) as target:
        for item in source.infolist():
            content = source.read(item.filename)
            if item.filename == "docProps/core.xml":
                core = ET.fromstring(content)
                revision = core.find(
                    "{http://schemas.openxmlformats.org/package/2006/metadata/core-properties}revision"
                )
                assert revision is not None
                revision.text = "2" if revision.text != "2" else "3"
                content = ET.tostring(core, encoding="utf-8", xml_declaration=True)
            target.writestr(item.filename, content)
    with zipfile.ZipFile(_TEMPLATE) as source, zipfile.ZipFile(template) as variant:
        assert source.read("word/document.xml") == variant.read("word/document.xml")
    registry, approvals, reference = _registered_template(tmp_path, template=template)
    report = _report()
    report["attachments"]["photo_ids"] = []
    report["attachments"].pop("photo_groups", None)

    generated = generate_docx(
        report, output_dir=str(tmp_path / "exports"),
        archive_manifest=_manifest(1), template_ref=reference,
        template_registry=registry, template_approvals=approvals,
    )

    assert Path(generated).is_file()
    assert compute_ooxml_package_fingerprint(template) != CURRENT_TEMPLATE_PACKAGE_FINGERPRINT


def database_rows(database, table):
    with database.connect() as connection:
        return [tuple(row) for row in connection.execute(f"SELECT * FROM {table}").fetchall()]
