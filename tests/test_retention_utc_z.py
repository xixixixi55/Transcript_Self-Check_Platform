"""Phase 5 基础写入的合成数据 UTC-Z 契约测试。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import (  # noqa: E402
    CaseRetentionRepository,
    CaseShellRepository,
    CleanupRunRepository,
    FormalWordArtifactRepository,
    RetentionPolicyRepository,
    SourceRecordRepository,
    TaskRecordRepository,
    WorkbenchDatabase,
)
from app.repository.workbench_database import normalize_utc_z, utc_now_z  # noqa: E402
from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402


def _database(tmp_path: Path) -> WorkbenchDatabase:
    return WorkbenchDatabase(tmp_path / "workbench.sqlite3", "SYNTHETIC-UTC-Z")


def _case(database: WorkbenchDatabase) -> None:
    CaseShellRepository(database).create({
        "case_id": "SYNTHETIC-CASE-UTC-Z",
        "case_name": "SYNTHETIC/TEST/UTC-Z",
        "case_summary": "SYNTHETIC",
        "source_id": "SYNTHETIC-SOURCE-UTC-Z",
        "parse_task_id": "SYNTHETIC-TASK-UTC-Z",
    })


def _verified_publication(database: WorkbenchDatabase) -> None:
    TaskRecordRepository(database).create({
        "task_id": "SYNTHETIC-TASK-UTC-Z", "case_id": "SYNTHETIC-CASE-UTC-Z",
        "kind": "archive", "status": "succeeded", "stage": "completed",
    })
    SourceRecordRepository(database).create({
        "source_id": "SYNTHETIC-SOURCE-UTC-Z", "case_id": "SYNTHETIC-CASE-UTC-Z",
        "task_id": "SYNTHETIC-TASK-UTC-Z", "source_type": "report_directory",
        "internal_path": "SYNTHETIC/TEST/source", "allowed_root": "SYNTHETIC/TEST",
        "allowed_root_id": "SYNTHETIC-ROOT", "fingerprint": "SYNTHETIC-FINGERPRINT", "metadata": {},
    })
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO archive_attempts(attempt_id,schema_version,case_id,task_id,"
            "deployment_instance_id,source_id,input_revision,source_revision,draft_revision,"
            "report_fingerprint,status,cleanup_status,created_at,revision) VALUES (?,?,?,?,?,?,?,?,?,?,?,'not_required',?,0)",
            ("SYNTHETIC-ATTEMPT-UTC-Z", 1, "SYNTHETIC-CASE-UTC-Z", "SYNTHETIC-TASK-UTC-Z",
             database.deployment_instance_id, "SYNTHETIC-SOURCE-UTC-Z", 0, 0, 0,
             "SYNTHETIC-REPORT", "succeeded", "2026-08-01T00:00:00Z"),
        )
        connection.execute(
            "INSERT INTO archive_publish_intents(intent_id,attempt_id,task_id,deployment_instance_id,"
            "case_id,source_id,source_revision,draft_revision,report_fingerprint,source_key,input_fingerprint,"
            "archive_fingerprint,manifest_id,relative_final_dir,public_manifest_json,publication_id,"
            "publication_relative_dir,publication_digest,publication_file_set_json,publication_status,fence_id,"
            "phase,publication_verified_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("SYNTHETIC-INTENT-UTC-Z", "SYNTHETIC-ATTEMPT-UTC-Z", "SYNTHETIC-TASK-UTC-Z",
             database.deployment_instance_id, "SYNTHETIC-CASE-UTC-Z", "SYNTHETIC-SOURCE-UTC-Z", 0, 0,
             "SYNTHETIC-REPORT", "SYNTHETIC-SOURCE-KEY", "SYNTHETIC-INPUT", "SYNTHETIC-ARCHIVE",
             "SYNTHETIC-MANIFEST", "formal", "{}", "SYNTHETIC-PUBLICATION-UTC-Z", "formal",
             "c" * 64, "[]", "verified", None, "verified", "2026-08-02T05:30:00Z",
             "2026-08-01T00:00:00Z", "2026-08-01T00:00:00Z"),
        )


def test_utc_z_helpers_normalize_offsets_and_reject_naive() -> None:
    assert utc_now_z().endswith("Z")
    assert not utc_now_z().endswith("+00:00")
    assert normalize_utc_z("2026-08-02T13:30:00+08:00") == "2026-08-02T05:30:00Z"
    assert normalize_utc_z("2026-08-02T00:30:00-05:00") == "2026-08-02T05:30:00Z"
    assert normalize_utc_z("2026-08-02T05:30:00.123456Z") == "2026-08-02T05:30:00.123456Z"
    with pytest.raises(WorkbenchPersistenceError):
        normalize_utc_z("2026-08-02T05:30:00")


def test_new_v11_retention_rows_store_canonical_z_times(tmp_path: Path) -> None:
    database = _database(tmp_path)
    _case(database)
    _verified_publication(database)

    policy = RetentionPolicyRepository(database).get()
    assert policy["created_at"].endswith("Z")
    assert policy["updated_at"].endswith("Z")

    retention = CaseRetentionRepository(database).upsert({
        "retention_record_id": "SYNTHETIC-RETENTION-UTC-Z",
        "case_id": "SYNTHETIC-CASE-UTC-Z",
        "last_meaningful_mutation_at": "2026-08-02T13:30:00+08:00",
        "retention_anchor_utc": "2026-08-02T05:30:00Z",
        "expires_at_utc": "2026-09-01T05:30:00Z",
        "policy_revision": 1,
        "case_revision": 0,
    })
    assert retention["last_meaningful_mutation_at"] == "2026-08-02T05:30:00Z"
    assert retention["created_at"].endswith("Z")
    assert retention["updated_at"].endswith("Z")

    word = FormalWordArtifactRepository(database).create({
        "word_artifact_id": "SYNTHETIC-WORD-UTC-Z",
        "case_id": "SYNTHETIC-CASE-UTC-Z",
        "publication_id": "SYNTHETIC-PUBLICATION-UTC-Z",
        "internal_relative_path": "formal/SYNTHETIC-CASE-UTC-Z.docx",
        "file_digest": "a" * 64,
        "file_size": 1,
        "source_manifest_digest": "b" * 64,
        "template_identity": "legacy",
        "template_version": "v1",
        "generated_at": "2026-08-02T13:30:00+08:00",
        "verified_at": "2026-08-02T00:30:00-05:00",
        "status": "verified",
    })
    assert word["generated_at"] == "2026-08-02T05:30:00Z"
    assert word["verified_at"] == "2026-08-02T05:30:00Z"
    assert word["created_at"].endswith("Z")
    assert word["updated_at"].endswith("Z")

    runs = CleanupRunRepository(database)
    run = runs.create_planned({
        "cleanup_run_id": "SYNTHETIC-CLEANUP-UTC-Z",
        "case_id": "SYNTHETIC-CASE-UTC-Z",
        "case_revision_at_plan": 0,
        "lease_expires_at": "2026-08-02T13:30:00+08:00",
    })
    assert run["lease_expires_at"] == "2026-08-02T05:30:00Z"
    assert run["created_at"].endswith("Z")
    assert run["updated_at"].endswith("Z")
    claimed = runs.claim(
        run["cleanup_run_id"], owner_instance_id="SYNTHETIC-OWNER-UTC-Z",
        claim_token="SYNTHETIC-CLAIM-UTC-Z", lease_expires_at="2026-08-02T14:30:00+08:00",
        expected_case_revision=0, now="2026-08-02T05:30:00Z",
    )
    assert claimed["lease_expires_at"] == "2026-08-02T06:30:00Z"
    assert claimed["updated_at"].endswith("Z")

    with database.connect() as connection:
        for table in (
            "case_retention_policies", "case_retention_records",
            "case_cleanup_runs", "formal_word_artifacts",
        ):
            sql = str(connection.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()[0]).upper()
            assert "CURRENT_TIMESTAMP" not in sql
            assert "DATETIME('NOW')" not in sql
