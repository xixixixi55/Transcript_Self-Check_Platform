"""Synthetic contract matrix for retention authority and time safety."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
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
from app.repository.workbench_constants import RETENTION_BLOCKER_CODES  # noqa: E402
from app.repository.retention_time import expires_at_utc, trusted_utc_timestamp  # noqa: E402
from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402


def test_trusted_utc_time_has_fail_closed_future_boundary() -> None:
    now = datetime(2026, 8, 2, 5, 30, tzinfo=timezone.utc)
    assert trusted_utc_timestamp("2026-08-02T13:30:00+08:00", now=now) == "2026-08-02T05:30:00Z"
    assert trusted_utc_timestamp("2026-08-02T05:35:00Z", now=now) == "2026-08-02T05:35:00Z"
    with pytest.raises(WorkbenchPersistenceError, match="RETENTION_TIME_IN_FUTURE"):
        trusted_utc_timestamp("2026-08-02T05:35:01Z", now=now)
    with pytest.raises(WorkbenchPersistenceError, match="RETENTION_TIME_INVALID"):
        trusted_utc_timestamp("2026-08-02T05:30:00", now=now)
    with pytest.raises(WorkbenchPersistenceError, match="RETENTION_TIME_IN_FUTURE"):
        expires_at_utc("2026-08-02T05:35:01Z", 30, now=now)


def test_expiry_is_continuous_utc_days_and_validates_policy_range() -> None:
    assert expires_at_utc("2026-08-02T13:30:00+08:00", 30) == "2026-09-01T05:30:00Z"
    with pytest.raises(WorkbenchPersistenceError, match="INVALID_RETENTION_DAYS"):
        expires_at_utc("2026-08-02T05:30:00Z", 0)


@pytest.mark.parametrize("code", [
    "RETENTION_ACTIVE_TASK", "RETENTION_ACTIVE_LEASE", "RETENTION_RECOVERY_IN_PROGRESS",
    "RETENTION_PUBLICATION_MISSING", "RETENTION_PUBLICATION_UNVERIFIED",
    "RETENTION_WORD_ARTIFACT_MISSING", "RETENTION_WORD_ARTIFACT_UNVERIFIED",
    "RETENTION_SNAPSHOT_ACTIVE", "RETENTION_SNAPSHOT_RECOVERY_REFERENCED",
    "RETENTION_SNAPSHOT_OWNERSHIP_UNKNOWN", "RETENTION_OWNERSHIP_UNKNOWN",
    "RETENTION_AUTHORITY_INCONSISTENT", "RETENTION_NOT_EXPIRED",
])
def test_blocker_matrix_keeps_stable_fail_closed_codes(code: str) -> None:
    assert code in RETENTION_BLOCKER_CODES


def test_formal_word_projection_does_not_create_competing_authority(tmp_path: Path) -> None:
    database = WorkbenchDatabase(tmp_path / "workbench.sqlite3", "SYNTHETIC-AUTHORITY")
    CaseShellRepository(database).create({
        "case_id": "SYNTHETIC-CASE-AUTHORITY",
        "case_name": "SYNTHETIC/TEST/Authority",
        "case_summary": "SYNTHETIC",
        "source_id": "SYNTHETIC-SOURCE-AUTHORITY",
        "parse_task_id": "SYNTHETIC-TASK-AUTHORITY",
    })
    repository = FormalWordArtifactRepository(database)
    with pytest.raises(WorkbenchPersistenceError, match="WORD_ARTIFACT_PUBLICATION_NOT_FOUND"):
        repository.create({
            "word_artifact_id": "SYNTHETIC-WORD-ORPHAN",
            "case_id": "SYNTHETIC-CASE-AUTHORITY",
            "publication_id": "SYNTHETIC-PUBLICATION-MISSING",
            "internal_relative_path": "formal/SYNTHETIC-ORPHAN.docx",
            "file_digest": "a" * 64,
            "file_size": 1,
            "source_manifest_digest": "b" * 64,
            "template_identity": "legacy",
            "template_version": "v1",
            "generated_at": "2026-08-01T00:00:00Z",
        })
    TaskRecordRepository(database).create({
        "task_id": "SYNTHETIC-TASK-AUTHORITY", "case_id": "SYNTHETIC-CASE-AUTHORITY",
        "kind": "archive", "status": "succeeded", "stage": "completed",
    })
    SourceRecordRepository(database).create({
        "source_id": "SYNTHETIC-SOURCE-AUTHORITY", "case_id": "SYNTHETIC-CASE-AUTHORITY",
        "task_id": "SYNTHETIC-TASK-AUTHORITY", "source_type": "report_directory",
        "internal_path": "SYNTHETIC/TEST/source", "allowed_root": "SYNTHETIC/TEST",
        "allowed_root_id": "SYNTHETIC-ROOT", "fingerprint": "SYNTHETIC-FINGERPRINT", "metadata": {},
    })
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO archive_attempts(attempt_id,schema_version,case_id,task_id,"
            "deployment_instance_id,source_id,input_revision,source_revision,draft_revision,"
            "report_fingerprint,status,cleanup_status,created_at,revision) VALUES (?,?,?,?,?,?,?,?,?,?,?,'not_required',?,0)",
            ("SYNTHETIC-ATTEMPT-AUTHORITY", 1, "SYNTHETIC-CASE-AUTHORITY", "SYNTHETIC-TASK-AUTHORITY",
             database.deployment_instance_id, "SYNTHETIC-SOURCE-AUTHORITY", 0, 0, 0,
             "SYNTHETIC-REPORT", "succeeded", "2026-08-01T00:00:00Z"),
        )
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO archive_publish_intents(intent_id,attempt_id,task_id,deployment_instance_id,"
            "case_id,source_id,source_revision,draft_revision,report_fingerprint,source_key,input_fingerprint,"
            "archive_fingerprint,manifest_id,relative_final_dir,public_manifest_json,publication_id,"
            "publication_relative_dir,publication_digest,publication_file_set_json,publication_status,fence_id,"
            "phase,publication_verified_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("SYNTHETIC-INTENT-AUTHORITY", "SYNTHETIC-ATTEMPT-AUTHORITY", "SYNTHETIC-TASK-AUTHORITY",
             "SYNTHETIC-AUTHORITY", "SYNTHETIC-CASE-AUTHORITY", "SYNTHETIC-SOURCE-AUTHORITY", 0, 0,
             "SYNTHETIC-REPORT", "SYNTHETIC-SOURCE-KEY", "SYNTHETIC-INPUT", "SYNTHETIC-ARCHIVE",
             "SYNTHETIC-MANIFEST", "formal", "{}", "SYNTHETIC-PUBLICATION-AUTHORITY", "formal",
             "c" * 64, "[]", "verified", "SYNTHETIC-FENCE-AUTHORITY", "verified",
             "2026-08-01T00:00:00Z", "2026-08-01T00:00:00Z", "2026-08-01T00:00:00Z"),
        )
    artifact = repository.create({
        "word_artifact_id": "SYNTHETIC-WORD-AUTHORITY",
        "case_id": "SYNTHETIC-CASE-AUTHORITY",
        "publication_id": "SYNTHETIC-PUBLICATION-AUTHORITY",
        "internal_relative_path": "formal/SYNTHETIC-AUTHORITY.docx",
        "file_digest": "a" * 64,
        "file_size": 1,
        "source_manifest_digest": "b" * 64,
        "template_identity": "legacy",
        "template_version": "v1",
        "generated_at": "2026-08-01T00:00:00Z",
    })
    assert artifact["publication_id"] == "SYNTHETIC-PUBLICATION-AUTHORITY"
    assert "formal_artifact_authority" not in database.table_names()
    assert "internal_relative_path" not in repository.get_public(
        "SYNTHETIC-WORD-AUTHORITY"
    )
