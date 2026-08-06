"""定向测试：统一导出（Word + RAR + HashMyFiles HTML + 审计记录）。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import (  # noqa: E402
    CaseShellRepository,
    WorkbenchDatabase,
    database_path_for_deployment,
)
from app.services import unified_export_service  # noqa: E402
from app.services.unified_export_service import (  # noqa: E402
    UnifiedExportError,
    unified_export,
)

CASE_ID = "SYNTHETIC-UNIFIED-EXPORT-CASE"


@pytest.fixture()
def database(tmp_path: Path) -> WorkbenchDatabase:
    db = WorkbenchDatabase(
        database_path_for_deployment(tmp_path, "SYNTHETIC-UNIFIED-EXPORT"),
        "SYNTHETIC-UNIFIED-EXPORT",
    )
    CaseShellRepository(db).create({
        "case_id": CASE_ID, "case_name": "SYNTHETIC/TEST/Export",
        "case_summary": "SYNTHETIC/TEST", "source_id": "SYNTHETIC-SOURCE",
        "parse_task_id": "SYNTHETIC-PARSE",
    })
    return db


def manifest() -> dict:
    return {
        "manifest_id": "SYNTHETIC-MANIFEST-1",
        "parts": [
            {
                "filename": "SYNTHETIC-CASE.part1.rar", "size_bytes": 4,
                "md5": "a" * 32, "disc_number": "GP20260718-01", "disc_date": "2026-07-18",
            },
            {
                "filename": "SYNTHETIC-CASE.part2.rar", "size_bytes": 4,
                "md5": "b" * 32, "disc_number": "GP20260718-02", "disc_date": "2026-07-18",
            },
        ],
    }


def fake_docx(report, *, photo_paths, output_dir, archive_manifest, **template_context):
    path = Path(output_dir) / "SYNTHETIC-CASE.docx"
    path.write_bytes(b"SYNTHETIC/DOCX")
    return str(path)


def fake_hash(rar_paths, output_dir):
    (Path(output_dir) / "hash.html").write_text("<html/>")
    return "hash.html"


def test_unified_export_writes_bundle_and_audit(database, tmp_path, monkeypatch) -> None:
    final_dir = tmp_path / "SYNTHETIC-FINAL"
    final_dir.mkdir(parents=True)
    for name in ("SYNTHETIC-CASE.part1.rar", "SYNTHETIC-CASE.part2.rar"):
        (final_dir / name).write_bytes(b"SYNTHETIC/RAR")

    monkeypatch.setattr(unified_export_service, "generate_docx", fake_docx)
    export_path = tmp_path / "SYNTHETIC-EXPORT-TARGET"

    result = unified_export(
        report={"introduction": {"case_summary": "SYNTHETIC"}},
        manifest=manifest(),
        final_dir=final_dir,
        export_path=export_path,
        photo_paths=[],
        template_context={},
        database=database,
        case_id=CASE_ID,
        task_id="SYNTHETIC-MANIFEST-1",
        hash_runner=fake_hash,
    )

    assert result["word_filename"] == "SYNTHETIC-CASE.docx"
    assert result["rar_filenames"] == ["SYNTHETIC-CASE.part1.rar", "SYNTHETIC-CASE.part2.rar"]
    assert result["hash_verification_html"] == "hash.html"
    assert (export_path / "SYNTHETIC-CASE.docx").exists()
    assert (export_path / "SYNTHETIC-CASE.part1.rar").exists()
    assert (export_path / "hash.html").exists()


def test_unified_export_requires_disc_mapping(database, tmp_path) -> None:
    final_dir = tmp_path / "SYNTHETIC-FINAL-2"
    final_dir.mkdir(parents=True)
    m = manifest()
    m["parts"][1]["disc_number"] = ""
    with pytest.raises(UnifiedExportError) as error:
        unified_export(
            report={}, manifest=m, final_dir=final_dir,
            export_path=tmp_path / "out", photo_paths=[], template_context={},
            hash_runner=fake_hash,
        )
    assert error.value.code == "DISC_MAPPING_INCOMPLETE"


def test_unified_export_missing_part_fails(database, tmp_path) -> None:
    final_dir = tmp_path / "SYNTHETIC-FINAL-3"
    final_dir.mkdir(parents=True)
    (final_dir / "SYNTHETIC-CASE.part1.rar").write_bytes(b"x")
    with pytest.raises(UnifiedExportError) as error:
        unified_export(
            report={}, manifest=manifest(), final_dir=final_dir,
            export_path=tmp_path / "out", photo_paths=[], template_context={},
            hash_runner=fake_hash,
        )
    assert error.value.code == "ARCHIVE_PART_MISSING"
