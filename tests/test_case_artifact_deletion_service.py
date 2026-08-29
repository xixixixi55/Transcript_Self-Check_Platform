"""显式删除自有工件的合成数据回归覆盖测试。"""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import WorkbenchDatabase, database_path_for_deployment  # noqa: E402
from app.repository.archive.archive_manifest_repository import ArchiveManifestRepository  # noqa: E402
from app.repository.formal_word_artifact_repository import FormalWordArtifactRepository  # noqa: E402
from app.services.archive.archive_authorization_service import ArchiveAuthorizationService  # noqa: E402
from app.services.case.case_artifact_deletion_service import CaseArtifactDeletionService  # noqa: E402
from app.services.case.case_draft_service import CaseDraftService  # noqa: E402
from app.services.case.case_lifecycle_service import CaseLifecycleService  # noqa: E402
from app.services.source_record_service import SourceRecordService  # noqa: E402
from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402

REPORT = {
    "title": "SYNTHETIC/TEST/InspectionReport",
    "document_number": "SYNTHETIC-DOC-DELETE",
    "introduction": {"case_summary": "SYNTHETIC", "evidence_list": [], "inspectors": []},
    "inspection": {"result": {}}, "attachments": {"photo_ids": []},
}


def _case(database: WorkbenchDatabase, tmp_path: Path) -> tuple[dict[str, str], Path]:
    allowed = tmp_path / "SYNTHETIC-ALLOWED-ROOT"
    output = tmp_path / "SYNTHETIC-PARSE-OUTPUT"
    report_dir = allowed / "SYNTHETIC-REPORT"
    (report_dir / "data").mkdir(parents=True)
    for filename in ("data_case_info.json", "data_report_info.json"):
        (report_dir / "data" / filename).write_text(json.dumps({"contents": []}), encoding="utf-8")
    (report_dir / "data" / "data_device_lists.json").write_text(
        json.dumps({"contents": [{"c3": "SYNTHETIC-C3"}]}), encoding="utf-8",
    )
    sources = SourceRecordService(
        database, ArchiveAuthorizationService(str(allowed), str(output)),
    )
    cases = CaseDraftService(
        database, parser=lambda _path, _output: {"report": copy.deepcopy(REPORT)},
        source_service=sources,
    )
    descriptor = sources.register_report_directory(str(report_dir))
    return cases.submit(descriptor, case_name="SYNTHETIC-DELETE-CASE"), report_dir


def _add_formal_rows(database: WorkbenchDatabase, identifiers: dict[str, str]) -> tuple[str, str]:
    case_id = identifiers["case_id"]
    attempt_id = "attempt-SYNTHETIC-FORMAL-DELETE"
    intent_id = "intent-SYNTHETIC-FORMAL-DELETE"
    publication_id = "publication-SYNTHETIC-FORMAL-DELETE"
    fence_id = "fence-SYNTHETIC-FORMAL-DELETE"
    now = "2026-08-05T00:00:00Z"
    manifest_id = "manifest-SYNTHETIC-FORMAL-DELETE"
    relative_dir = "SYNTHETIC-ARCHIVE-UUID/SYNTHETIC-MANIFEST-FORMAL-DELETE"
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO archive_attempts(attempt_id,schema_version,case_id,task_id,deployment_instance_id,source_id,"
            "input_revision,source_revision,draft_revision,report_fingerprint,status,cleanup_status,created_at,revision) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,'not_required',?,0)",
            (attempt_id, 1, case_id, identifiers["task_id"], database.deployment_instance_id,
             identifiers["source_id"], 0, 0, 0, "SYNTHETIC-REPORT", "succeeded", now),
        )
        connection.execute(
            "INSERT INTO archive_context_bindings(context_hash,attempt_id,case_id,source_id,source_revision,"
            "draft_revision,report_fingerprint,context_kind,active,expires_at,consumed_at,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("SYNTHETIC-CONTEXT-FORMAL-DELETE", attempt_id, case_id, identifiers["source_id"],
             0, 0, "SYNTHETIC-REPORT", "workbench", 0, None, now, now),
        )
        connection.execute(
            "INSERT INTO archive_publish_fences(fence_id,attempt_id,task_id,deployment_instance_id,case_id,source_id,"
            "source_revision,draft_revision,report_fingerprint,context_hash,shell_revision,status,reason,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (fence_id, attempt_id, identifiers["task_id"], database.deployment_instance_id, case_id,
             identifiers["source_id"], 0, 0, "SYNTHETIC-REPORT", "SYNTHETIC-CONTEXT-FORMAL-DELETE",
             0, "consumed", None, now, now),
        )
        connection.execute(
            "INSERT INTO archive_publish_intents(intent_id,attempt_id,task_id,deployment_instance_id,case_id,source_id,"
            "source_revision,draft_revision,report_fingerprint,source_key,input_fingerprint,archive_fingerprint,manifest_id,"
            "relative_final_dir,public_manifest_json,publication_id,publication_relative_dir,publication_digest,"
            "publication_file_set_json,publication_status,fence_id,phase,publication_verified_at,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (intent_id, attempt_id, identifiers["task_id"], database.deployment_instance_id, case_id,
             identifiers["source_id"], 0, 0, "SYNTHETIC-REPORT", "SYNTHETIC-SOURCE", "SYNTHETIC-INPUT",
             "SYNTHETIC-ARCHIVE", manifest_id, relative_dir, json.dumps({"manifest_id": manifest_id}),
             publication_id, relative_dir, "a" * 64, "[]", "verified", fence_id, "verified", now, now, now),
        )
    FormalWordArtifactRepository(database).create({
        "word_artifact_id": "word-SYNTHETIC-FORMAL-DELETE", "case_id": case_id,
        "publication_id": publication_id, "internal_relative_path": "formal/SYNTHETIC-DELETE.docx",
        "file_digest": "b" * 64, "file_size": 8, "source_manifest_digest": "c" * 64,
        "template_identity": "legacy", "template_version": "v1", "generated_at": now,
        "verified_at": now, "status": "verified",
    })
    return attempt_id, relative_dir


def test_explicit_delete_removes_formal_archive_word_and_case_assets_but_keeps_source(
    tmp_path: Path,
) -> None:
    database = WorkbenchDatabase(
        database_path_for_deployment(tmp_path, "SYNTHETIC-DEPLOYMENT"), "SYNTHETIC-DEPLOYMENT",
    )
    identifiers, source_dir = _case(database, tmp_path)
    output_root = tmp_path / "SYNTHETIC-OUTPUT"
    attempt_id, relative_dir = _add_formal_rows(database, identifiers)
    final_dir = output_root / "compressed" / relative_dir
    final_dir.mkdir(parents=True)
    (final_dir / "SYNTHETIC-volume.rar").write_bytes(b"SYNTHETIC/TEST/RAR")
    ArchiveManifestRepository(output_root).save(
        source_key="f" * 64, input_fingerprint="d" * 64,
        archive_fingerprint="e" * 64, manifest_id="manifest-SYNTHETIC-FORMAL-DELETE",
        final_dir=final_dir, public_manifest={"manifest_id": "manifest-SYNTHETIC-FORMAL-DELETE"},
        workbench_attempt_id=attempt_id, publication_id="publication-SYNTHETIC-FORMAL-DELETE",
        publication_digest="a" * 64,
    )
    word_path = output_root / "exports" / "formal" / "SYNTHETIC-DELETE.docx"
    word_path.parent.mkdir(parents=True)
    word_path.write_bytes(b"SYNTHETIC")
    asset_path = database.database_path.parent / "assets" / identifiers["case_id"] / "asset-SYNTHETIC.png"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_bytes(b"SYNTHETIC/TEST/IMAGE")

    lifecycle = CaseLifecycleService(
        database, artifact_deletion_service=CaseArtifactDeletionService(database, output_root),
    )
    assert lifecycle.delete_case(identifiers["case_id"]) == {
        "case_id": identifiers["case_id"], "deleted": True,
    }
    assert not final_dir.exists()
    assert not final_dir.parent.exists()
    assert not word_path.exists()
    assert not asset_path.exists()
    assert source_dir.exists()
    assert ArchiveManifestRepository(output_root).find_for_attempt(attempt_id) == []


def test_delete_rejects_a_persisted_artifact_locator_outside_controlled_roots(
    tmp_path: Path,
) -> None:
    database = WorkbenchDatabase(
        database_path_for_deployment(tmp_path, "SYNTHETIC-DEPLOYMENT"), "SYNTHETIC-DEPLOYMENT",
    )
    identifiers, source_dir = _case(database, tmp_path)
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO archive_attempts(attempt_id,schema_version,case_id,task_id,deployment_instance_id,source_id,"
            "input_revision,status,cleanup_status,staging_locator,created_at,revision) "
            "VALUES (?,?,?,?,?,?,?,'accepted','pending',?,?,0)",
            ("attempt-SYNTHETIC-ESCAPE", 1, identifiers["case_id"], identifiers["task_id"],
             database.deployment_instance_id, identifiers["source_id"], 0, str(tmp_path / "SYNTHETIC-OUTSIDE"),
             "2026-08-05T00:00:00Z"),
        )

    lifecycle = CaseLifecycleService(
        database, artifact_deletion_service=CaseArtifactDeletionService(database, tmp_path / "SYNTHETIC-OUTPUT"),
    )
    with pytest.raises(WorkbenchPersistenceError, match="CASE_DELETE_FAILED"):
        lifecycle.delete_case(identifiers["case_id"])
    assert source_dir.exists()
    with database.connect() as connection:
        assert connection.execute(
            "SELECT 1 FROM case_shells WHERE case_id=?", (identifiers["case_id"],)
        ).fetchone() is not None


def test_explicit_delete_removes_incomplete_archive_records_with_context_binding(
    tmp_path: Path,
) -> None:
    database = WorkbenchDatabase(
        database_path_for_deployment(tmp_path, "SYNTHETIC-DEPLOYMENT"), "SYNTHETIC-DEPLOYMENT",
    )
    identifiers, source_dir = _case(database, tmp_path)
    output_root = tmp_path / "SYNTHETIC-OUTPUT"
    attempt_id = "attempt-SYNTHETIC-INCOMPLETE-DELETE"
    context_hash = "SYNTHETIC-CONTEXT-INCOMPLETE-DELETE"
    now = "2026-08-05T00:00:00Z"
    staging_dir = output_root / "compressed" / ".staging" / attempt_id
    snapshot_dir = output_root / "compressed" / ".inputs" / attempt_id
    snapshot_copying_dir = snapshot_dir.parent / f".{snapshot_dir.name}.copying"
    snapshot_marker = snapshot_dir.parent / f".{snapshot_dir.name}.owner.json"
    staging_dir.mkdir(parents=True)
    snapshot_dir.mkdir(parents=True)
    snapshot_copying_dir.mkdir(parents=True)
    (staging_dir / "SYNTHETIC-partial.rar").write_bytes(b"SYNTHETIC")
    (snapshot_dir / "SYNTHETIC-input.json").write_text("SYNTHETIC", encoding="utf-8")
    (snapshot_copying_dir / "SYNTHETIC-partial.json").write_text("SYNTHETIC", encoding="utf-8")
    snapshot_marker.write_text("SYNTHETIC", encoding="utf-8")
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO archive_attempts(attempt_id,schema_version,case_id,task_id,deployment_instance_id,source_id,"
            "input_revision,status,cleanup_status,staging_locator,input_snapshot_locator,created_at,revision) "
            "VALUES (?,?,?,?,?,?,?,'interrupted','pending',?,?,?,0)",
            (attempt_id, 1, identifiers["case_id"], identifiers["task_id"], database.deployment_instance_id,
             identifiers["source_id"], 0, str(staging_dir), f".inputs/{attempt_id}", now),
        )
        connection.execute(
            "INSERT INTO archive_context_bindings(context_hash,attempt_id,case_id,source_id,source_revision,"
            "draft_revision,report_fingerprint,context_kind,active,expires_at,consumed_at,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (context_hash, attempt_id, identifiers["case_id"], identifiers["source_id"],
             0, 0, "SYNTHETIC-REPORT", "workbench", 1, None, None, now),
        )

    lifecycle = CaseLifecycleService(
        database, artifact_deletion_service=CaseArtifactDeletionService(database, output_root),
    )
    assert lifecycle.delete_case(identifiers["case_id"]) == {
        "case_id": identifiers["case_id"], "deleted": True,
    }
    assert not staging_dir.exists()
    assert not snapshot_dir.exists()
    assert not snapshot_copying_dir.exists()
    assert not snapshot_marker.exists()
    assert source_dir.exists()


def test_delete_accepts_staging_from_one_of_multiple_controlled_archive_roots(
    tmp_path: Path,
) -> None:
    database = WorkbenchDatabase(
        database_path_for_deployment(tmp_path, "SYNTHETIC-DEPLOYMENT"), "SYNTHETIC-DEPLOYMENT",
    )
    identifiers, source_dir = _case(database, tmp_path)
    active_output_root = tmp_path / "SYNTHETIC-ACTIVE-OUTPUT"
    legacy_output_root = tmp_path / "SYNTHETIC-LEGACY-OUTPUT"
    portable_output_root = tmp_path / "SYNTHETIC-PORTABLE-OUTPUT"
    attempt_id = "attempt-SYNTHETIC-MULTI-ROOT-DELETE"
    staging_dir = portable_output_root / "compressed" / ".staging" / attempt_id
    staging_dir.mkdir(parents=True)
    (staging_dir / "SYNTHETIC-partial.rar").write_bytes(b"SYNTHETIC")
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO archive_attempts(attempt_id,schema_version,case_id,task_id,deployment_instance_id,source_id,"
            "input_revision,status,cleanup_status,staging_locator,created_at,revision) "
            "VALUES (?,?,?,?,?,?,?,'succeeded','succeeded',?,?,0)",
            (attempt_id, 1, identifiers["case_id"], identifiers["task_id"],
             database.deployment_instance_id, identifiers["source_id"], 0, str(staging_dir),
             "2026-08-21T00:00:00Z"),
        )

    lifecycle = CaseLifecycleService(
        database,
        artifact_deletion_service=CaseArtifactDeletionService(
            database,
            legacy_output_root,
            archive_output_roots=(
                active_output_root,
                legacy_output_root,
                portable_output_root,
            ),
        ),
    )

    assert lifecycle.delete_case(identifiers["case_id"]) == {
        "case_id": identifiers["case_id"], "deleted": True,
    }
    assert not staging_dir.exists()
    assert source_dir.exists()


def test_explicit_delete_removes_short_snapshot_and_owner_artifacts(
    tmp_path: Path,
) -> None:
    database = WorkbenchDatabase(
        database_path_for_deployment(tmp_path, "SYNTHETIC-DEPLOYMENT"), "SYNTHETIC-DEPLOYMENT",
    )
    identifiers, source_dir = _case(database, tmp_path)
    output_root = tmp_path / "SYNTHETIC-OUTPUT"
    snapshot_name = "sSYNTHETIC-SHORT"
    snapshot_root = output_root / ".i"
    snapshot_dir = snapshot_root / snapshot_name
    snapshot_copying_dir = snapshot_root / f".{snapshot_name}.copying"
    snapshot_marker = snapshot_root / f".{snapshot_name}.owner.json"
    snapshot_dir.mkdir(parents=True)
    snapshot_copying_dir.mkdir(parents=True)
    (snapshot_dir / "SYNTHETIC-input.json").write_text("SYNTHETIC", encoding="utf-8")
    (snapshot_copying_dir / "SYNTHETIC-partial.json").write_text("SYNTHETIC", encoding="utf-8")
    snapshot_marker.write_text("SYNTHETIC", encoding="utf-8")
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO archive_attempts(attempt_id,schema_version,case_id,task_id,deployment_instance_id,source_id,"
            "input_revision,status,cleanup_status,input_snapshot_locator,created_at,revision) "
            "VALUES (?,?,?,?,?,?,?,'interrupted','pending',?,?,0)",
            ("attempt-SYNTHETIC-SHORT-DELETE", 1, identifiers["case_id"], identifiers["task_id"],
             database.deployment_instance_id, identifiers["source_id"], 0, f".i/{snapshot_name}",
             "2026-08-05T00:00:00Z"),
        )

    lifecycle = CaseLifecycleService(
        database, artifact_deletion_service=CaseArtifactDeletionService(database, output_root),
    )
    assert lifecycle.delete_case(identifiers["case_id"]) == {
        "case_id": identifiers["case_id"], "deleted": True,
    }
    assert not snapshot_dir.exists()
    assert not snapshot_copying_dir.exists()
    assert not snapshot_marker.exists()
    assert source_dir.exists()
