"""持久正式 Word 工件仓储的合成数据测试。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import (  # noqa: E402
    CaseShellRepository,
    FormalWordArtifactRepository,
    SourceRecordRepository,
    TaskRecordRepository,
    WorkbenchDatabase,
)
from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402


_TIME = "2026-08-01T00:00:00Z"


def _database(tmp_path: Path, deployment: str = "SYNTHETIC-WORD") -> WorkbenchDatabase:
    return WorkbenchDatabase(tmp_path / f"{deployment}.sqlite3", deployment)


def _publication(database: WorkbenchDatabase) -> tuple[str, str]:
    case_id = "SYNTHETIC-CASE-WORD"
    task_id = "SYNTHETIC-TASK-WORD"
    source_id = "SYNTHETIC-SOURCE-WORD"
    attempt_id = "SYNTHETIC-ATTEMPT-WORD"
    publication_id = "SYNTHETIC-PUBLICATION-WORD"
    CaseShellRepository(database).create({
        "case_id": case_id, "case_name": "SYNTHETIC/TEST/Word",
        "case_summary": "SYNTHETIC", "source_id": source_id,
        "parse_task_id": task_id,
    })
    TaskRecordRepository(database).create({
        "task_id": task_id, "case_id": case_id, "kind": "archive",
        "status": "succeeded", "stage": "completed",
    })
    SourceRecordRepository(database).create({
        "source_id": source_id, "case_id": case_id, "task_id": task_id,
        "source_type": "report_directory", "internal_path": "SYNTHETIC/TEST/source",
        "allowed_root": "SYNTHETIC/TEST", "allowed_root_id": "SYNTHETIC-ROOT",
        "fingerprint": "SYNTHETIC-FINGERPRINT", "metadata": {},
    })
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO archive_attempts(attempt_id,schema_version,case_id,task_id,"
            "deployment_instance_id,source_id,input_revision,source_revision,draft_revision,"
            "report_fingerprint,status,cleanup_status,created_at,revision) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,'not_required',?,0)",
            (attempt_id, 1, case_id, task_id, database.deployment_instance_id, source_id,
             0, 0, 0, "SYNTHETIC-REPORT", "succeeded", _TIME),
        )
        connection.execute(
            "INSERT INTO archive_publish_intents(intent_id,attempt_id,task_id,"
            "deployment_instance_id,case_id,source_id,source_revision,draft_revision,"
            "report_fingerprint,source_key,input_fingerprint,archive_fingerprint,manifest_id,"
            "relative_final_dir,public_manifest_json,publication_id,publication_relative_dir,"
            "publication_digest,publication_file_set_json,publication_status,fence_id,phase,"
            "publication_verified_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("SYNTHETIC-INTENT-WORD", attempt_id, task_id, database.deployment_instance_id,
             case_id, source_id, 0, 0, "SYNTHETIC-REPORT", "SYNTHETIC-SOURCE-KEY",
             "SYNTHETIC-INPUT", "SYNTHETIC-ARCHIVE", "SYNTHETIC-MANIFEST", "formal", "{}",
             publication_id, "formal", "c" * 64, "[]", "verified", "SYNTHETIC-FENCE-WORD",
             "verified", None, _TIME, _TIME),
        )
    return case_id, publication_id


def _artifact(repository: FormalWordArtifactRepository, case_id: str, publication_id: str) -> dict[str, object]:
    return repository.create({
        "word_artifact_id": "SYNTHETIC-WORD-001", "case_id": case_id,
        "publication_id": publication_id, "internal_relative_path": "formal/SYNTHETIC.docx",
        "file_digest": "a" * 64, "file_size": 123, "source_manifest_digest": "b" * 64,
        "template_identity": "legacy", "template_version": "v1", "generated_at": _TIME,
    })


def _mark_publication_verified(database: WorkbenchDatabase) -> None:
    with database.transaction() as connection:
        connection.execute(
            "UPDATE archive_publish_intents SET publication_verified_at=? "
            "WHERE publication_id=? AND deployment_instance_id=?",
            (_TIME, "SYNTHETIC-PUBLICATION-WORD", database.deployment_instance_id),
        )


def test_word_artifact_survives_restart_with_safe_public_projection(tmp_path: Path) -> None:
    database = _database(tmp_path)
    case_id, publication_id = _publication(database)
    artifact = _artifact(FormalWordArtifactRepository(database), case_id, publication_id)

    restarted = _database(tmp_path)
    internal = FormalWordArtifactRepository(restarted).get_internal(str(artifact["word_artifact_id"]))
    public = FormalWordArtifactRepository(restarted).get_public(str(artifact["word_artifact_id"]))

    assert internal["file_digest"] == "a" * 64
    assert internal["file_size"] == 123
    assert internal["source_manifest_digest"] == "b" * 64
    assert internal["internal_relative_path"] == "formal/SYNTHETIC.docx"
    assert "internal_relative_path" not in public
    assert "report_json" not in internal


@pytest.mark.parametrize(
    ("field", "value"),
    [("file_digest", "not-a-sha256"), ("source_manifest_digest", "f" * 63),
     ("file_size", -1), ("file_size", True), ("file_size", 2**53)],
)
def test_word_artifact_rejects_invalid_digest_or_size(
    tmp_path: Path, field: str, value: object,
) -> None:
    database = _database(tmp_path)
    case_id, publication_id = _publication(database)
    payload: dict[str, object] = {
        "word_artifact_id": f"SYNTHETIC-WORD-{field}", "case_id": case_id,
        "publication_id": publication_id, "internal_relative_path": "formal/SYNTHETIC.docx",
        "file_digest": "a" * 64, "file_size": 123, "source_manifest_digest": "b" * 64,
        "template_identity": "legacy", "template_version": "v1", "generated_at": _TIME,
    }
    payload[field] = value
    with pytest.raises(WorkbenchPersistenceError, match="INVALID_WORD_ARTIFACT"):
        FormalWordArtifactRepository(database).create(payload)


@pytest.mark.parametrize(
    ("status", "verified_at"),
    [("verified", None), ("pending", _TIME), ("invalid", _TIME)],
)
def test_word_artifact_status_and_verified_time_are_consistent(
    tmp_path: Path, status: str, verified_at: str | None,
) -> None:
    database = _database(tmp_path)
    case_id, publication_id = _publication(database)
    payload = {
        "word_artifact_id": f"SYNTHETIC-WORD-{status}", "case_id": case_id,
        "publication_id": publication_id, "internal_relative_path": "formal/SYNTHETIC.docx",
        "file_digest": "a" * 64, "file_size": 1, "source_manifest_digest": "b" * 64,
        "template_identity": "legacy", "template_version": "v1", "generated_at": _TIME,
        "status": status, "verified_at": verified_at,
    }
    with pytest.raises(WorkbenchPersistenceError, match="INVALID_WORD_ARTIFACT"):
        FormalWordArtifactRepository(database).create(payload)


def test_verified_word_artifact_revalidates_publication_on_read(tmp_path: Path) -> None:
    database = _database(tmp_path)
    case_id, publication_id = _publication(database)
    _mark_publication_verified(database)
    artifact = FormalWordArtifactRepository(database).create({
        "word_artifact_id": "SYNTHETIC-WORD-VERIFIED", "case_id": case_id,
        "publication_id": publication_id, "internal_relative_path": "formal/SYNTHETIC.docx",
        "file_digest": "a" * 64, "file_size": 1, "source_manifest_digest": "b" * 64,
        "template_identity": "legacy", "template_version": "v1", "generated_at": _TIME,
        "status": "verified", "verified_at": _TIME,
    })
    assert artifact["status"] == "verified"
    with database.transaction() as connection:
        connection.execute(
            "UPDATE archive_publish_intents SET publication_verified_at=NULL "
            "WHERE publication_id=? AND deployment_instance_id=?",
            (publication_id, database.deployment_instance_id),
        )
    with pytest.raises(WorkbenchPersistenceError, match="WORD_ARTIFACT_PUBLICATION_UNVERIFIED"):
        FormalWordArtifactRepository(database).get_public("SYNTHETIC-WORD-VERIFIED")


def test_orphan_file_and_publication_fail_closed(tmp_path: Path) -> None:
    database = _database(tmp_path)
    case_id, _publication_id = _publication(database)
    orphan = tmp_path / "orphan-SYNTHETIC.docx"
    orphan.write_bytes(b"SYNTHETIC-ORPHAN")
    repository = FormalWordArtifactRepository(database)

    with pytest.raises(WorkbenchPersistenceError, match="WORD_ARTIFACT_NOT_FOUND"):
        repository.get_internal("SYNTHETIC-ORPHAN-WORD")
    with pytest.raises(WorkbenchPersistenceError, match="WORD_ARTIFACT_PUBLICATION_NOT_FOUND"):
        repository.create({
            "word_artifact_id": "SYNTHETIC-WORD-MISSING-PUBLICATION", "case_id": case_id,
            "publication_id": "SYNTHETIC-PUBLICATION-MISSING",
            "internal_relative_path": "formal/SYNTHETIC-ORPHAN.docx",
            "file_digest": "a" * 64, "file_size": 16, "source_manifest_digest": "b" * 64,
            "template_identity": "legacy", "template_version": "v1", "generated_at": _TIME,
        })
