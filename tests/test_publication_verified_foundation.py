"""Slice 5A-1 publication verification CAS foundation tests."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import CaseShellRepository, SourceRecordRepository, TaskRecordRepository, WorkbenchDatabase  # noqa: E402
from app.repository.archive_publish_intent_repository import ArchivePublishIntentRepository  # noqa: E402
from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402


def _database(tmp_path: Path) -> WorkbenchDatabase:
    return WorkbenchDatabase(tmp_path / "workbench.sqlite3", "SYNTHETIC-PUBLICATION")


def _case(database: WorkbenchDatabase) -> None:
    CaseShellRepository(database).create({
        "case_id": "SYNTHETIC-CASE-PUBLICATION",
        "case_name": "SYNTHETIC/TEST/Publication",
        "case_summary": "SYNTHETIC",
        "source_id": "SYNTHETIC-SOURCE-PUBLICATION",
        "parse_task_id": "SYNTHETIC-TASK-PUBLICATION",
    })


def _publication(
    tmp_path: Path, *, publication_status: str = "verified", phase: str = "verified",
    digest: str = "c" * 64,
) -> tuple[WorkbenchDatabase, ArchivePublishIntentRepository, str, list[dict[str, int | str]]]:
    database = _database(tmp_path)
    _case(database)
    TaskRecordRepository(database).create({
        "task_id": "SYNTHETIC-TASK-PUBLICATION", "case_id": "SYNTHETIC-CASE-PUBLICATION",
        "kind": "archive", "status": "succeeded", "stage": "completed",
    })
    SourceRecordRepository(database).create({
        "source_id": "SYNTHETIC-SOURCE-PUBLICATION", "case_id": "SYNTHETIC-CASE-PUBLICATION",
        "task_id": "SYNTHETIC-TASK-PUBLICATION", "source_type": "report_directory",
        "internal_path": "SYNTHETIC/TEST/source", "allowed_root": "SYNTHETIC/TEST",
        "allowed_root_id": "SYNTHETIC-ROOT", "fingerprint": "SYNTHETIC-FINGERPRINT", "metadata": {},
    })
    file_set = [{"name": "SYNTHETIC.rar", "size": 1}]
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO archive_attempts(attempt_id,schema_version,case_id,task_id,"
            "deployment_instance_id,source_id,input_revision,source_revision,draft_revision,"
            "report_fingerprint,status,cleanup_status,created_at,revision) VALUES (?,?,?,?,?,?,?,?,?,?,?,'not_required',?,0)",
            ("SYNTHETIC-ATTEMPT-PUBLICATION", 1, "SYNTHETIC-CASE-PUBLICATION",
             "SYNTHETIC-TASK-PUBLICATION", database.deployment_instance_id,
             "SYNTHETIC-SOURCE-PUBLICATION", 0, 0, 0, "SYNTHETIC-REPORT", "succeeded",
             "2026-08-01T00:00:00Z"),
        )
        connection.execute(
            "INSERT INTO archive_publish_fences(fence_id,attempt_id,task_id,deployment_instance_id,"
            "case_id,source_id,source_revision,draft_revision,report_fingerprint,context_hash,"
            "shell_revision,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,'active',?,?)",
            ("SYNTHETIC-FENCE-PUBLICATION", "SYNTHETIC-ATTEMPT-PUBLICATION", "SYNTHETIC-TASK-PUBLICATION",
             database.deployment_instance_id, "SYNTHETIC-CASE-PUBLICATION", "SYNTHETIC-SOURCE-PUBLICATION",
             0, 0, "SYNTHETIC-REPORT", "SYNTHETIC-CONTEXT", 0,
             "2026-08-01T00:00:00Z", "2026-08-01T00:00:00Z"),
        )
        connection.execute(
            "INSERT INTO archive_publish_intents(intent_id,attempt_id,task_id,deployment_instance_id,"
            "case_id,source_id,source_revision,draft_revision,report_fingerprint,source_key,"
            "input_fingerprint,archive_fingerprint,manifest_id,relative_final_dir,public_manifest_json,"
            "publication_id,publication_relative_dir,publication_digest,publication_file_set_json,"
            "publication_status,fence_id,phase,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("SYNTHETIC-INTENT-PUBLICATION", "SYNTHETIC-ATTEMPT-PUBLICATION", "SYNTHETIC-TASK-PUBLICATION",
             database.deployment_instance_id, "SYNTHETIC-CASE-PUBLICATION", "SYNTHETIC-SOURCE-PUBLICATION",
             0, 0, "SYNTHETIC-REPORT", "SYNTHETIC-SOURCE-KEY", "SYNTHETIC-INPUT",
             "SYNTHETIC-ARCHIVE", "SYNTHETIC-MANIFEST", "formal", "{}", "SYNTHETIC-PUBLICATION-001",
             "formal", digest, json.dumps(file_set, separators=(",", ":")),
             publication_status, "SYNTHETIC-FENCE-PUBLICATION", phase, "2026-08-01T00:00:00Z",
             "2026-08-01T00:00:00Z"),
        )
    return database, ArchivePublishIntentRepository(database), digest, file_set


def _assert_blocked(
    database: WorkbenchDatabase, repository: ArchivePublishIntentRepository, digest: str,
    file_set: list[dict[str, int | str]], *, fence_id: str = "SYNTHETIC-FENCE-PUBLICATION",
) -> None:
    with pytest.raises(WorkbenchPersistenceError) as error:
        repository.mark_publication_verified(
            "SYNTHETIC-PUBLICATION-001", "2026-08-01T00:01:00Z", publication_digest=digest,
            file_set=file_set, fence_id=fence_id, case_id="SYNTHETIC-CASE-PUBLICATION",
        )
    assert error.value.code == "ARCHIVE_PUBLICATION_VERIFICATION_BLOCKED"
    with database.connect() as connection:
        assert connection.execute(
            "SELECT publication_verified_at FROM archive_publish_intents"
        ).fetchone()[0] is None


def test_publication_verified_at_is_nullable_and_null_only(tmp_path: Path) -> None:
    database, repository, digest, file_set = _publication(tmp_path)
    first = repository.mark_publication_verified(
        "SYNTHETIC-PUBLICATION-001", "2026-08-01T00:01:00+00:00", publication_digest=digest,
        file_set=file_set,
        fence_id="SYNTHETIC-FENCE-PUBLICATION", case_id="SYNTHETIC-CASE-PUBLICATION",
    )
    second = repository.mark_publication_verified(
        "SYNTHETIC-PUBLICATION-001", "2026-08-02T00:01:00Z", publication_digest=digest,
        file_set=file_set,
        fence_id="SYNTHETIC-FENCE-PUBLICATION", case_id="SYNTHETIC-CASE-PUBLICATION",
    )
    assert first["publication_verified_at"] == "2026-08-01T00:01:00Z"
    assert second["publication_verified_at"] == first["publication_verified_at"]


def test_indexed_phase_is_rejected_even_when_status_is_published(tmp_path: Path) -> None:
    database, repository, digest, file_set = _publication(tmp_path, publication_status="published", phase="indexed")
    _assert_blocked(database, repository, digest, file_set)


def test_indexed_phase_is_rejected_even_when_status_is_verified(tmp_path: Path) -> None:
    database, repository, digest, file_set = _publication(tmp_path, phase="indexed")
    _assert_blocked(database, repository, digest, file_set)


def test_digest_mismatch_is_rejected(tmp_path: Path) -> None:
    database, repository, digest, file_set = _publication(tmp_path)
    _assert_blocked(database, repository, "d" * 64, file_set)


def test_file_set_mismatch_is_rejected(tmp_path: Path) -> None:
    database, repository, digest, file_set = _publication(tmp_path)
    _assert_blocked(database, repository, digest, [{"name": "SYNTHETIC.md5", "size": 1}])


def test_fence_mismatch_is_rejected(tmp_path: Path) -> None:
    database, repository, digest, file_set = _publication(tmp_path)
    _assert_blocked(database, repository, digest, file_set, fence_id="SYNTHETIC-FENCE-OTHER")
