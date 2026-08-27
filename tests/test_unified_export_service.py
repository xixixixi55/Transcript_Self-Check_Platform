"""定向测试：统一导出（Word + RAR + 审计记录）。"""

from __future__ import annotations

import os
import json
import sys
import threading
import time
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
from app.services.attachment_plan_models_service import AttachmentPlanError  # noqa: E402

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


def test_attachment_mapping_error_is_not_wrapped_as_generic_word_failure(
    tmp_path, monkeypatch,
) -> None:
    def invalid_mapping(*_args, **_kwargs):
        raise AttachmentPlanError(
            "ATTACHMENT2_IMAGE_MAPPING_INVALID",
            "附件2图片必须明确归属检材并保持审核后的顺序。",
        )

    monkeypatch.setattr(unified_export_service, "generate_docx", invalid_mapping)
    with pytest.raises(UnifiedExportError) as error:
        unified_export_service._export_word(
            {}, {}, tmp_path, [], {}, "SYNTHETIC.docx",
        )

    assert error.value.code == "ATTACHMENT2_IMAGE_MAPPING_INVALID"
    assert "明确归属检材" in str(error.value)


def test_unified_export_writes_bundle_and_audit(database, tmp_path, monkeypatch) -> None:
    final_dir = tmp_path / "SYNTHETIC-FINAL"
    final_dir.mkdir(parents=True)
    for name in ("SYNTHETIC-CASE.part1.rar", "SYNTHETIC-CASE.part2.rar"):
        (final_dir / name).write_bytes(b"SYNTHETIC/RAR")

    monkeypatch.setattr(unified_export_service, "generate_docx", fake_docx)
    export_path = tmp_path / "SYNTHETIC-EXPORT-TARGET"
    export_path.mkdir()
    (export_path / "SYNTHETIC-CASE.part1.rar").write_bytes(b"SYNTHETIC/OLD-RAR")
    (export_path / "SYNTHETIC-CASE.part2.rar").write_bytes(b"SYNTHETIC/OLD-RAR")
    (export_path / "hash-verification.png").write_bytes(b"SYNTHETIC/OLD-PNG")
    (export_path / "hash-verification.html").write_bytes(b"SYNTHETIC/OLD-HTML")

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
    )

    assert result["word_filename"] == "SYNTHETIC-CASE.docx"
    assert result["rar_filenames"] == ["SYNTHETIC-CASE.part1.rar", "SYNTHETIC-CASE.part2.rar"]
    assert "hash_verification_image" not in result
    assert (export_path / "SYNTHETIC-CASE.docx").exists()
    assert (export_path / "SYNTHETIC-CASE.part1.rar").read_bytes() == b"SYNTHETIC/RAR"
    assert (export_path / "SYNTHETIC-CASE.part2.rar").read_bytes() == b"SYNTHETIC/RAR"
    assert not (export_path / "hash-verification.png").exists()
    assert not (export_path / "hash-verification.html").exists()
    assert not (export_path.parent / "SYNTHETIC-CASE.part1.rar").exists()
    assert not (export_path.parent / "SYNTHETIC-CASE.part2.rar").exists()
    connection = database.connect()
    try:
        payload = json.loads(connection.execute(
            "SELECT payload_json FROM audit_events WHERE event_type = 'unified_export'",
        ).fetchone()[0])
    finally:
        connection.close()
    assert "hash_verification_image" not in payload
    assert "hash_verification_html" not in payload


def test_unified_export_does_not_invoke_hashmyfiles_screenshot(tmp_path, monkeypatch) -> None:
    final_dir = tmp_path / "SYNTHETIC-FINAL-NO-HASH-SCREENSHOT"
    final_dir.mkdir()
    for name in ("SYNTHETIC-CASE.part1.rar", "SYNTHETIC-CASE.part2.rar"):
        (final_dir / name).write_bytes(b"SYNTHETIC/RAR")
    export_path = tmp_path / "SYNTHETIC-EXPORT-NO-HASH-SCREENSHOT"
    export_path.mkdir()

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("统一导出不得调用 HashMyFiles 截图机制")

    monkeypatch.setattr(unified_export_service, "generate_docx", fake_docx)
    monkeypatch.setattr(
        unified_export_service, "generate_verification_image", fail_if_called,
        raising=False,
    )

    result = unified_export(
        report={"introduction": {"case_summary": "SYNTHETIC"}},
        manifest=manifest(), final_dir=final_dir,
        export_path=export_path, photo_paths=[], template_context={},
    )

    assert result["rar_filenames"] == [
        "SYNTHETIC-CASE.part1.rar", "SYNTHETIC-CASE.part2.rar",
    ]
    assert not list(export_path.glob("*.png"))


def test_bundle_publish_failure_rolls_back_every_replaced_file(tmp_path, monkeypatch) -> None:
    staging = tmp_path / "staging"
    export = tmp_path / "export"
    staging.mkdir(); export.mkdir()
    for name in ("report.docx", "part1.rar"):
        (staging / name).write_bytes(f"NEW-{name}".encode())
        (export / name).write_bytes(f"OLD-{name}".encode())
    legacy_png = export / "hash-verification.png"
    legacy_png.write_bytes(b"LEGACY-hash-verification.png")
    legacy_html = export / "hash-verification.html"
    legacy_html.write_bytes(b"LEGACY-hash-verification.html")
    real_replace = unified_export_service.os.replace

    def fail_second_publish(source, target):
        source_path, target_path = Path(source), Path(target)
        if source_path.parent == staging and source_path.name == "part1.rar":
            raise OSError("SYNTHETIC/PUBLISH-FAILURE")
        return real_replace(source_path, target_path)

    monkeypatch.setattr(unified_export_service.os, "replace", fail_second_publish)
    with pytest.raises(UnifiedExportError) as error:
        unified_export_service._publish_staged_bundle(
            staging, export, ["report.docx", "part1.rar"],
        )

    assert error.value.code == "EXPORT_PUBLISH_FAILED"
    for name in ("report.docx", "part1.rar"):
        assert (export / name).read_bytes() == f"OLD-{name}".encode()
    assert legacy_png.read_bytes() == b"LEGACY-hash-verification.png"
    assert legacy_html.read_bytes() == b"LEGACY-hash-verification.html"


def test_bundle_publish_serializes_concurrent_writes_to_same_directory(
    tmp_path, monkeypatch,
) -> None:
    export = tmp_path / "SYNTHETIC-SHARED-EXPORT"
    staging_paths = [tmp_path / "staging-1", tmp_path / "staging-2"]
    export.mkdir()
    for index, staging in enumerate(staging_paths, start=1):
        staging.mkdir()
        (staging / "report.docx").write_bytes(f"SYNTHETIC/DOCX/{index}".encode())
        (staging / "part1.rar").write_bytes(f"SYNTHETIC/RAR/{index}".encode())

    real_replace = unified_export_service.os.replace
    activity_lock = threading.Lock()
    start = threading.Barrier(3)
    active_replaces = 0
    max_active_replaces = 0
    completed_publishes = 0
    publish_errors: list[BaseException] = []

    def observed_replace(source, target):
        nonlocal active_replaces, max_active_replaces
        with activity_lock:
            active_replaces += 1
            max_active_replaces = max(max_active_replaces, active_replaces)
        time.sleep(0.02)
        try:
            return real_replace(source, target)
        finally:
            with activity_lock:
                active_replaces -= 1

    def publish(staging: Path) -> None:
        nonlocal completed_publishes
        try:
            start.wait()
            unified_export_service._publish_staged_bundle(
                staging, export, ["report.docx", "part1.rar"],
            )
            with activity_lock:
                completed_publishes += 1
        except BaseException as error:
            with activity_lock:
                publish_errors.append(error)

    monkeypatch.setattr(unified_export_service.os, "replace", observed_replace)
    threads = [threading.Thread(target=publish, args=(staging,)) for staging in staging_paths]
    for thread in threads:
        thread.start()
    start.wait()
    for thread in threads:
        thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    assert publish_errors == []
    assert completed_publishes == 2
    assert max_active_replaces == 1
    published_versions = {
        (export / "report.docx").read_bytes().rsplit(b"/", 1)[-1],
        (export / "part1.rar").read_bytes().rsplit(b"/", 1)[-1],
    }
    assert len(published_versions) == 1


def test_unified_export_forwards_user_word_filename(database, tmp_path, monkeypatch) -> None:
    """REQ-009: the unified export uses the user-chosen Word file name."""
    final_dir = tmp_path / "SYNTHETIC-FINAL-5"
    final_dir.mkdir(parents=True)
    for name in ("SYNTHETIC-CASE.part1.rar", "SYNTHETIC-CASE.part2.rar"):
        (final_dir / name).write_bytes(b"SYNTHETIC/RAR")
    captured: dict[str, object] = {}

    def fake_docx(report, *, photo_paths, output_dir, archive_manifest,
                  output_filename=None, **template_context):
        captured["output_filename"] = output_filename
        path = Path(output_dir) / (output_filename or "SYNTHETIC-CASE.docx")
        path.write_bytes(b"SYNTHETIC/DOCX")
        return str(path)

    monkeypatch.setattr(unified_export_service, "generate_docx", fake_docx)
    export_path = tmp_path / "SYNTHETIC-EXPORT-TARGET-5"
    result = unified_export(
        report={"introduction": {"case_summary": "SYNTHETIC"}},
        manifest=manifest(), final_dir=final_dir, export_path=export_path,
        photo_paths=[], template_context={},
        word_filename="用户命名.docx",
    )
    assert captured["output_filename"] == "用户命名.docx"
    assert result["word_filename"] == "用户命名.docx"
    assert (export_path / "用户命名.docx").exists()


def test_unified_export_requires_disc_mapping(database, tmp_path) -> None:
    final_dir = tmp_path / "SYNTHETIC-FINAL-2"
    final_dir.mkdir(parents=True)
    m = manifest()
    m["parts"][1]["disc_number"] = ""
    with pytest.raises(UnifiedExportError) as error:
        unified_export(
            report={}, manifest=m, final_dir=final_dir,
            export_path=tmp_path / "out", photo_paths=[], template_context={},
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
        )
    assert error.value.code == "ARCHIVE_PART_MISSING"


def test_unified_export_layers_deferred_discs_onto_word_manifest(database, tmp_path, monkeypatch) -> None:
    """REQ-030/MF-3: after disc-mapping, Word gets the layered disc metadata."""
    final_dir = tmp_path / "SYNTHETIC-FINAL-4"
    final_dir.mkdir(parents=True)
    for name in ("SYNTHETIC-CASE.part1.rar", "SYNTHETIC-CASE.part2.rar"):
        (final_dir / name).write_bytes(b"SYNTHETIC/RAR")
    empty = manifest()
    for part in empty["parts"]:
        part["disc_number"] = ""
        part["disc_date"] = ""
    plan = {
        "volume_slots": [
            {"status": "active", "ordinal": 1, "disc_mapping": {"disc_number": "GP20260718-01", "disc_date": "2026-07-18", "confirmation": "confirmed"}},
            {"status": "active", "ordinal": 2, "disc_mapping": {"disc_number": "GP20260718-02", "disc_date": "2026-07-18", "confirmation": "confirmed"}},
        ]
    }
    captured: dict[str, object] = {}

    def fake_docx(report, *, photo_paths, output_dir, archive_manifest, **template_context):
        captured["manifest"] = archive_manifest
        path = Path(output_dir) / "SYNTHETIC-CASE.docx"
        path.write_bytes(b"SYNTHETIC/DOCX")
        return str(path)

    monkeypatch.setattr(unified_export_service, "generate_docx", fake_docx)
    export_path = tmp_path / "SYNTHETIC-EXPORT-TARGET-4"
    result = unified_export(
        report={"introduction": {"case_summary": "SYNTHETIC"}},
        manifest=empty, final_dir=final_dir, export_path=export_path,
        photo_paths=[], template_context={}, plan=plan,
    )
    assert captured["manifest"]["parts"][0]["disc_number"] == "GP20260718-01"
    assert captured["manifest"]["parts"][0]["disc_date"] == "2026-07-18"
    assert captured["manifest"]["parts"][1]["disc_number"] == "GP20260718-02"
    assert result["word_filename"] == "SYNTHETIC-CASE.docx"


def test_unified_export_rejects_pending_disc_mapping(database, tmp_path) -> None:
    plan = {
        "volume_slots": [{
            "status": "pending", "ordinal": 1,
            "disc_mapping": {
                "disc_number": "GP20260718-01", "disc_date": "2026-07-18",
                "confirmation": "pending",
            },
        }],
    }
    with pytest.raises(UnifiedExportError) as error:
        unified_export(
            report={}, manifest=manifest(), final_dir=tmp_path,
            export_path=tmp_path / "out", photo_paths=[], template_context={},
            plan=plan,
        )
    assert error.value.code == "DISC_MAPPING_INCOMPLETE"
