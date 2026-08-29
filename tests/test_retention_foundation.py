"""共享契约与 v11 持久事实的 Slice 5A-1 合成数据测试。"""

from __future__ import annotations

import json
import os
import sqlite3
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
from app.repository.archive.archive_publish_intent_repository import ArchivePublishIntentRepository  # noqa: E402
from app.repository.retention_policy_config import parse_retention_environment  # noqa: E402
from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402
from app.repository.workbench_constants import WORKBENCH_SCHEMA_VERSION  # noqa: E402
from app.repository.workbench_schema import MIGRATIONS  # noqa: E402


def _database(tmp_path: Path) -> WorkbenchDatabase:
    return WorkbenchDatabase(tmp_path / "workbench.sqlite3", "SYNTHETIC-RETENTION")


def _case(database: WorkbenchDatabase) -> None:
    CaseShellRepository(database).create({
        "case_id": "SYNTHETIC-CASE-RETENTION",
        "case_name": "SYNTHETIC/TEST/Retention",
        "case_summary": "SYNTHETIC",
        "source_id": "SYNTHETIC-SOURCE-RETENTION",
        "parse_task_id": "SYNTHETIC-TASK-RETENTION",
    })


def _publication_authority(database: WorkbenchDatabase) -> None:
    TaskRecordRepository(database).create({
        "task_id": "SYNTHETIC-TASK-RETENTION", "case_id": "SYNTHETIC-CASE-RETENTION",
        "kind": "archive", "status": "succeeded", "stage": "completed",
    })
    SourceRecordRepository(database).create({
        "source_id": "SYNTHETIC-SOURCE-RETENTION", "case_id": "SYNTHETIC-CASE-RETENTION",
        "task_id": "SYNTHETIC-TASK-RETENTION", "source_type": "report_directory",
        "internal_path": "SYNTHETIC/TEST/source", "allowed_root": "SYNTHETIC/TEST",
        "allowed_root_id": "SYNTHETIC-ROOT", "fingerprint": "SYNTHETIC-FINGERPRINT", "metadata": {},
    })
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO archive_attempts(attempt_id,schema_version,case_id,task_id,"
            "deployment_instance_id,source_id,input_revision,source_revision,draft_revision,"
            "report_fingerprint,status,cleanup_status,created_at,revision) VALUES (?,?,?,?,?,?,?,?,?,?,?,'not_required',?,0)",
            ("SYNTHETIC-ATTEMPT-RETENTION", 1, "SYNTHETIC-CASE-RETENTION",
             "SYNTHETIC-TASK-RETENTION", database.deployment_instance_id,
             "SYNTHETIC-SOURCE-RETENTION", 0, 0, 0, "SYNTHETIC-REPORT", "succeeded",
             "2026-08-01T00:00:00Z"),
        )
        connection.execute(
            "INSERT INTO archive_publish_intents(intent_id,attempt_id,task_id,deployment_instance_id,"
            "case_id,source_id,source_revision,draft_revision,report_fingerprint,source_key,input_fingerprint,"
            "archive_fingerprint,manifest_id,relative_final_dir,public_manifest_json,publication_id,"
            "publication_relative_dir,publication_digest,publication_file_set_json,publication_status,fence_id,"
            "phase,publication_verified_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("SYNTHETIC-INTENT-RETENTION", "SYNTHETIC-ATTEMPT-RETENTION", "SYNTHETIC-TASK-RETENTION",
             database.deployment_instance_id, "SYNTHETIC-CASE-RETENTION", "SYNTHETIC-SOURCE-RETENTION",
             0, 0, "SYNTHETIC-REPORT", "SYNTHETIC-SOURCE-KEY", "SYNTHETIC-INPUT", "SYNTHETIC-ARCHIVE",
             "SYNTHETIC-MANIFEST", "formal", "{}", "SYNTHETIC-PUBLICATION-001", "formal",
             "c" * 64, "[]", "verified", None, "verified", None,
             "2026-08-01T00:00:00Z", "2026-08-01T00:00:00Z"),
        )


def test_v11_schema_has_safe_defaults_and_no_cleanup_run(tmp_path: Path) -> None:
    database = _database(tmp_path)
    assert WORKBENCH_SCHEMA_VERSION == 11
    assert database.schema_version() == 11
    assert {
        "case_retention_policies", "case_retention_records", "case_cleanup_runs",
        "formal_word_artifacts",
    }.issubset(database.table_names())
    with database.connect() as connection:
        policy = connection.execute("SELECT * FROM case_retention_policies").fetchone()
        assert policy["mode"] == "disabled"
        assert policy["retention_days"] == 30
        assert policy["scan_interval_seconds"] == 86400
        assert policy["batch_size"] == 20
        assert connection.execute("SELECT COUNT(*) FROM case_cleanup_runs").fetchone()[0] == 0
        assert connection.execute(
            "SELECT publication_verified_at FROM archive_publish_intents"
        ).fetchone() is None
        snapshot_fks = connection.execute(
            "PRAGMA foreign_key_list(archive_input_snapshots)"
        ).fetchall()
        source_fk = next(row for row in snapshot_fks if row[3] == "source_id")
        assert source_fk[2] == "source_records"
        source_info = {
            row[1]: row for row in connection.execute("PRAGMA table_info(archive_input_snapshots)")
        }
        assert source_info["source_id"][3] == 1


def test_v10_fixture_preserves_source_and_snapshot_identity_on_upgrade(tmp_path: Path) -> None:
    path = tmp_path / "SYNTHETIC-v10.sqlite3"
    with sqlite3.connect(path) as connection:
        for version, statements in MIGRATIONS:
            if version > 10:
                break
            for statement in statements:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",
                (version, "2026-08-01T00:00:00Z"),
            )
        connection.execute("PRAGMA user_version = 10")
        connection.execute(
            "INSERT INTO case_shells VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "SYNTHETIC-CASE-V10", 1, None, "SYNTHETIC/CASE", "SYNTHETIC",
                "SYNTHETIC-SOURCE-V10", "SYNTHETIC-TASK-V10", "archiving", 1, 0,
                "2026-08-01T00:00:00Z", "2026-08-01T00:00:00Z",
            ),
        )
        connection.execute(
            "INSERT INTO source_records(source_id,schema_version,case_id,task_id,source_type,"
            "internal_path,allowed_root,allowed_root_id,metadata_json,fingerprint_json,access_status,"
            "requires_reselection,revalidation_error_code,last_verified_at,revision,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "SYNTHETIC-SOURCE-V10", 1, "SYNTHETIC-CASE-V10", None, "report_directory",
                "SYNTHETIC/TEST/source", "SYNTHETIC/TEST", "SYNTHETIC-ROOT", "{}", "{}",
                "available", 0, None, "2026-08-01T00:00:00Z", 0,
                "2026-08-01T00:00:00Z", "2026-08-01T00:00:00Z",
            ),
        )
        connection.execute(
            "INSERT INTO archive_attempts(attempt_id,schema_version,case_id,source_id,input_revision,"
            "status,cleanup_status,created_at,revision) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                "SYNTHETIC-ATTEMPT-V10", 1, "SYNTHETIC-CASE-V10", "SYNTHETIC-SOURCE-V10",
                0, "succeeded", "not_required", "2026-08-01T00:00:00Z", 0,
            ),
        )
        connection.execute(
            "INSERT INTO archive_input_snapshots(snapshot_id,task_id,attempt_id,"
            "deployment_instance_id,case_id,source_id,source_revision,draft_revision,source_root_id,"
            "snapshot_root_id,snapshot_locator,manifest_json,input_fingerprint,status,marker_token,"
            "created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "SYNTHETIC-SNAPSHOT-V10", "SYNTHETIC-TASK-V10", "SYNTHETIC-ATTEMPT-V10",
                "SYNTHETIC-V10", "SYNTHETIC-CASE-V10", "SYNTHETIC-SOURCE-V10", 0, 0,
                "SYNTHETIC-ROOT", "SYNTHETIC-SNAPSHOT-ROOT", "SYNTHETIC/TEST/snapshot",
                "{}", "SYNTHETIC-FINGERPRINT", "sealed", "SYNTHETIC-MARKER",
                "2026-08-01T00:00:00Z", "2026-08-01T00:00:00Z",
            ),
        )
        connection.commit()
    database = WorkbenchDatabase(path, "SYNTHETIC-V10")
    with database.connect() as connection:
        assert connection.execute(
            "SELECT source_id FROM case_shells WHERE case_id='SYNTHETIC-CASE-V10'"
        ).fetchone()[0] == "SYNTHETIC-SOURCE-V10"
        assert connection.execute(
            "SELECT source_id FROM archive_attempts WHERE attempt_id='SYNTHETIC-ATTEMPT-V10'"
        ).fetchone()[0] == "SYNTHETIC-SOURCE-V10"
        assert connection.execute(
            "SELECT source_id FROM archive_input_snapshots WHERE snapshot_id='SYNTHETIC-SNAPSHOT-V10'"
        ).fetchone()[0] == "SYNTHETIC-SOURCE-V10"
        assert connection.execute("PRAGMA foreign_key_check").fetchone() is None
        assert connection.execute(
            "SELECT publication_verified_at FROM archive_publish_intents"
        ).fetchone() is None


def test_retention_config_is_pure_and_legacy_key_cannot_enable_cleanup() -> None:
    defaults = parse_retention_environment({})
    assert defaults.mode == "disabled"
    assert defaults.retention_days == 30
    assert defaults.scan_interval_seconds == 86400
    assert defaults.batch_size == 20

    legacy = parse_retention_environment(
        {"BIJI_CASE_RETENTION_MODE": "disabled"},
        legacy_days="45", allow_legacy_days=True,
    )
    assert legacy.retention_days == 45
    assert legacy.used_legacy_days is True
    assert legacy.mode == "disabled"

    invalid_new_days = parse_retention_environment(
        {"BIJI_CASE_RETENTION_MODE": "enforce", "BIJI_CASE_RETENTION_DAYS": "bad"},
        legacy_days="45", allow_legacy_days=True,
    )
    assert invalid_new_days.valid is False
    assert invalid_new_days.mode == "disabled"
    assert invalid_new_days.retention_days == 30
    assert invalid_new_days.used_legacy_days is False

    invalid_mode = parse_retention_environment({"BIJI_CASE_RETENTION_MODE": "delete"})
    assert invalid_mode.valid is False
    assert invalid_mode.mode == "disabled"


def test_policy_authority_sync_is_explicit_monotonic_and_stops_legacy_reads(tmp_path: Path) -> None:
    database = _database(tmp_path)
    repository = RetentionPolicyRepository(database)
    initial = repository.get()
    changed = repository.sync_from_environment({
        "BIJI_CASE_RETENTION_MODE": "preview_only",
        "BIJI_CASE_RETENTION_DAYS": "45",
        "BIJI_CASE_RETENTION_SCAN_INTERVAL_SECONDS": "3600",
        "BIJI_CASE_RETENTION_BATCH_SIZE": "10",
        "workbench.successful_case_retention_days": "999",
    })
    assert changed["mode"] == "preview_only"
    assert changed["retention_days"] == 45
    assert changed["policy_revision"] == initial["policy_revision"] + 1
    assert changed["activated_at"] == changed["updated_at"]

    unchanged = repository.sync_from_environment({
        "BIJI_CASE_RETENTION_MODE": "preview_only",
        "BIJI_CASE_RETENTION_DAYS": "45",
        "BIJI_CASE_RETENTION_SCAN_INTERVAL_SECONDS": "3600",
        "BIJI_CASE_RETENTION_BATCH_SIZE": "10",
        "workbench.successful_case_retention_days": "1",
    })
    assert unchanged["policy_revision"] == changed["policy_revision"]
    with pytest.raises(WorkbenchPersistenceError) as error:
        repository.sync_from_environment({
            "BIJI_CASE_RETENTION_MODE": "enforce",
            "BIJI_CASE_RETENTION_DAYS": "invalid",
            "workbench.successful_case_retention_days": "1",
        })
    assert error.value.code == "RETENTION_CONFIG_INVALID_DAYS"
    assert repository.get()["policy_revision"] == changed["policy_revision"]


def test_policy_row_is_authority_when_environment_changes(tmp_path: Path) -> None:
    database = _database(tmp_path)
    repository = RetentionPolicyRepository(database)
    repository.sync_from_environment({"BIJI_CASE_RETENTION_DAYS": "60"})
    durable = repository.get()
    assert repository.get()["retention_days"] == 60
    assert durable["mode"] == "disabled"
    assert repository.get()["retention_days"] != 30


def test_foundation_repositories_keep_public_projections_safe(tmp_path: Path) -> None:
    database = _database(tmp_path)
    _case(database)
    _publication_authority(database)
    policy = RetentionPolicyRepository(database).get()
    assert policy["mode"] == "disabled"

    retention = CaseRetentionRepository(database).upsert({
        "retention_record_id": "SYNTHETIC-RETENTION-RECORD",
        "case_id": "SYNTHETIC-CASE-RETENTION",
        "last_meaningful_mutation_at": "2026-07-01T00:00:00Z",
        "policy_revision": 1,
        "case_revision": 0,
    })
    assert retention["eligibility"] == "unknown"

    word = FormalWordArtifactRepository(database).create({
        "word_artifact_id": "SYNTHETIC-WORD-001",
        "case_id": "SYNTHETIC-CASE-RETENTION",
        "publication_id": "SYNTHETIC-PUBLICATION-001",
        "internal_relative_path": "formal/SYNTHETIC-CASE-RETENTION.docx",
        "file_digest": "a" * 64,
        "file_size": 123,
        "source_manifest_digest": "b" * 64,
        "template_identity": "legacy",
        "template_version": "v1",
        "generated_at": "2026-07-01T00:00:00Z",
    })
    public_word = FormalWordArtifactRepository(database).get_public(word["word_artifact_id"])
    assert "internal_relative_path" not in public_word
    assert public_word["word_artifact_id"] == "SYNTHETIC-WORD-001"

    runs = CleanupRunRepository(database)
    run = runs.create_planned({
        "cleanup_run_id": "SYNTHETIC-CLEANUP-001",
        "case_id": "SYNTHETIC-CASE-RETENTION",
        "case_revision_at_plan": 0,
    })
    with pytest.raises(WorkbenchPersistenceError):
        runs.create_planned({
            "cleanup_run_id": "SYNTHETIC-CLEANUP-002",
            "case_id": "SYNTHETIC-CASE-RETENTION",
            "case_revision_at_plan": 0,
        })
    claimed = runs.claim(
        run["cleanup_run_id"], owner_instance_id="SYNTHETIC-OWNER",
        claim_token="SYNTHETIC-CLAIM", lease_expires_at="2026-08-01T00:00:00Z",
        expected_case_revision=0, now="2026-07-31T00:00:00Z",
    )
    public_run = runs.get_public(claimed["cleanup_run_id"])
    assert "claim_token" not in public_run
    assert "owner_instance_id" not in public_run
    assert public_run["phase"] == "claimed"
