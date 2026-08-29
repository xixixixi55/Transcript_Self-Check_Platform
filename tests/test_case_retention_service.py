"""任务 3.1 的合成数据保留服务契约测试。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import (  # noqa: E402
    CaseRetentionRepository,
    CaseShellRepository,
    FormalWordArtifactRepository,
    SourceRecordRepository,
    TaskRecordRepository,
    WorkbenchDatabase,
)
from app.repository.workbench.workbench_errors import WorkbenchPersistenceError  # noqa: E402
from app.services.archive.archive_publication_identity_service import (  # noqa: E402
    publication_digest,
    publication_file_set,
)
from app.services.case.case_retention_service import CaseRetentionService  # noqa: E402

CASE_ID = "SYNTHETIC-RETENTION-SERVICE-CASE"
SOURCE_ID = "SYNTHETIC-RETENTION-SERVICE-SOURCE"
TASK_ID = "SYNTHETIC-RETENTION-SERVICE-TASK"
ATTEMPT_ID = "SYNTHETIC-RETENTION-SERVICE-ATTEMPT"
FENCE_ID = "SYNTHETIC-RETENTION-SERVICE-FENCE"
INTENT_ID = "SYNTHETIC-RETENTION-SERVICE-INTENT"
PUBLICATION_ID = "SYNTHETIC-RETENTION-SERVICE-PUBLICATION"
WORD_ID = "SYNTHETIC-RETENTION-SERVICE-WORD"
MUTATION = "2026-07-01T00:00:00Z"
PUBLICATION_TIME = "2026-07-05T00:00:00Z"
WORD_TIME = "2026-07-10T00:00:00Z"
MANIFEST = {
    "manifest_id": "SYNTHETIC-MANIFEST",
    "validation_status": "validated",
    "parts": [{"filename": "SYNTHETIC-CASE.part1.rar", "size_bytes": 10, "md5": "a" * 32}],
}


def _database(tmp_path: Path) -> WorkbenchDatabase:
    return WorkbenchDatabase(tmp_path / "workbench.sqlite3", "SYNTHETIC-RETENTION-SERVICE")


def _prepare(database: WorkbenchDatabase, *, verified: bool = True) -> None:
    CaseShellRepository(database).create({
        "case_id": CASE_ID, "case_name": "SYNTHETIC/TEST/Retention service",
        "case_summary": "SYNTHETIC", "source_id": SOURCE_ID, "parse_task_id": "SYNTHETIC-PARSE-TASK",
    })
    TaskRecordRepository(database).create({
        "task_id": TASK_ID, "case_id": CASE_ID, "kind": "archive",
        "status": "succeeded", "stage": "completed",
    })
    SourceRecordRepository(database).create({
        "source_id": SOURCE_ID, "case_id": CASE_ID, "task_id": TASK_ID,
        "source_type": "report_directory", "internal_path": "SYNTHETIC/TEST/source",
        "allowed_root": "SYNTHETIC/TEST", "allowed_root_id": "SYNTHETIC-ROOT",
        "fingerprint": "SYNTHETIC-FINGERPRINT", "metadata": {},
    })
    file_set = publication_file_set(MANIFEST)
    intent = {
        "task_id": TASK_ID, "attempt_id": ATTEMPT_ID, "case_id": CASE_ID,
        "deployment_instance_id": database.deployment_instance_id, "source_id": SOURCE_ID,
        "source_revision": 0, "draft_revision": 0, "report_fingerprint": "SYNTHETIC-REPORT",
        "source_key": "SYNTHETIC-SOURCE-KEY", "input_fingerprint": "SYNTHETIC-INPUT",
        "archive_fingerprint": "SYNTHETIC-ARCHIVE", "manifest_id": MANIFEST["manifest_id"],
        "relative_final_dir": "SYNTHETIC/TEST/formal", "publication_id": PUBLICATION_ID,
        "fence_id": FENCE_ID,
    }
    digest, _ = publication_digest(intent, MANIFEST)
    publication_time = PUBLICATION_TIME if verified else None
    with database.transaction() as connection:
        connection.execute(
            "UPDATE case_shells SET lifecycle='exported',revision=1 WHERE case_id=?",
            (CASE_ID,),
        )
        connection.execute(
            "INSERT INTO archive_attempts(attempt_id,schema_version,case_id,task_id,deployment_instance_id,source_id,"
            "input_revision,source_revision,draft_revision,report_fingerprint,status,cleanup_status,created_at,revision) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,'not_required',?,0)",
            (ATTEMPT_ID, 1, CASE_ID, TASK_ID, database.deployment_instance_id, SOURCE_ID,
             0, 0, 0, "SYNTHETIC-REPORT", "succeeded", MUTATION),
        )
        connection.execute(
            "INSERT INTO archive_publish_fences(fence_id,attempt_id,task_id,deployment_instance_id,case_id,source_id,"
            "source_revision,draft_revision,report_fingerprint,context_hash,shell_revision,status,reason,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (FENCE_ID, ATTEMPT_ID, TASK_ID, database.deployment_instance_id, CASE_ID, SOURCE_ID,
             0, 0, "SYNTHETIC-REPORT", "SYNTHETIC-CONTEXT", 1, "consumed", None, MUTATION, MUTATION),
        )
        connection.execute(
            "INSERT INTO archive_publish_intents(intent_id,attempt_id,task_id,deployment_instance_id,case_id,source_id,"
            "source_revision,draft_revision,report_fingerprint,source_key,input_fingerprint,archive_fingerprint,manifest_id,"
            "relative_final_dir,public_manifest_json,publication_id,publication_relative_dir,publication_digest,"
            "publication_file_set_json,publication_status,fence_id,phase,publication_verified_at,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (INTENT_ID, ATTEMPT_ID, TASK_ID, database.deployment_instance_id, CASE_ID, SOURCE_ID, 0, 0,
             "SYNTHETIC-REPORT", "SYNTHETIC-SOURCE-KEY", "SYNTHETIC-INPUT", "SYNTHETIC-ARCHIVE",
             MANIFEST["manifest_id"], "SYNTHETIC/TEST/formal", json.dumps(MANIFEST, sort_keys=True),
             PUBLICATION_ID, "SYNTHETIC/TEST/formal", digest, json.dumps(file_set, sort_keys=True, separators=(",", ":")),
             "verified", FENCE_ID, "verified", publication_time, MUTATION, MUTATION),
        )
    if verified:
        FormalWordArtifactRepository(database).create({
            "word_artifact_id": WORD_ID, "case_id": CASE_ID, "publication_id": PUBLICATION_ID,
            "internal_relative_path": "formal/SYNTHETIC-RETENTION-SERVICE.docx", "file_digest": "b" * 64,
            "file_size": 10, "source_manifest_digest": "c" * 64, "template_identity": "legacy",
            "template_version": "v1", "generated_at": WORD_TIME, "verified_at": WORD_TIME,
            "status": "verified",
        })
    else:
        FormalWordArtifactRepository(database).create({
            "word_artifact_id": WORD_ID, "case_id": CASE_ID, "publication_id": PUBLICATION_ID,
            "internal_relative_path": "formal/SYNTHETIC-RETENTION-SERVICE.docx", "file_digest": "b" * 64,
            "file_size": 10, "source_manifest_digest": "c" * 64, "template_identity": "legacy",
            "template_version": "v1", "generated_at": WORD_TIME, "status": "pending",
        })
    CaseRetentionRepository(database).upsert({
        "retention_record_id": "SYNTHETIC-RETENTION-SERVICE-RECORD", "case_id": CASE_ID,
        "last_meaningful_mutation_at": MUTATION, "policy_revision": 1, "case_revision": 1,
    })


def _facts(payload: dict[str, object], verified_at: str = "2026-08-01T00:00:00Z") -> dict[str, object]:
    return {
        "verified": True, "rar_verified": True, "manifest_verified": True,
        "md5_verified": True, "inventory_verified": True, "ownership_verified": True,
        "publication_digest": payload["publication_digest"], "publication_file_set": payload["publication_file_set"],
        "fence_id": payload["fence_id"], "case_id": payload["case_id"],
        "deployment_instance_id": payload["deployment_instance_id"], "verified_at": verified_at,
    }


def test_evaluate_computes_max_anchor_and_enforce_gate(tmp_path: Path) -> None:
    database = _database(tmp_path)
    _prepare(database)
    database_path = database.database_path
    from app.repository.retention.retention_policy_repository import RetentionPolicyRepository
    RetentionPolicyRepository(database).sync_from_environment({
        "BIJI_CASE_RETENTION_MODE": "enforce", "BIJI_CASE_RETENTION_DAYS": "30",
        "BIJI_CASE_RETENTION_SCAN_INTERVAL_SECONDS": "3600", "BIJI_CASE_RETENTION_BATCH_SIZE": "20",
    })
    result = CaseRetentionService(database).evaluate_case(CASE_ID, now="2026-09-01T00:00:00Z")
    assert result["eligibility"] == "eligible"
    assert result["retention_anchor_utc"] == WORD_TIME
    assert result["expires_at_utc"] == "2026-08-09T00:00:00Z"
    assert result["enforce_allowed"] is True
    assert result["policy_mode"] == "enforce"
    assert database_path.exists()


def test_historical_publication_requires_controlled_revalidation_and_keeps_null_on_failure(tmp_path: Path) -> None:
    database = _database(tmp_path)
    _prepare(database, verified=False)
    service = CaseRetentionService(database)
    result = service.evaluate_case(CASE_ID, now="2026-09-01T00:00:00Z")
    assert result["last_blocker_code"] == "RETENTION_PUBLICATION_UNVERIFIED"
    with database.connect() as connection:
        assert connection.execute(
            "SELECT publication_verified_at FROM archive_publish_intents WHERE publication_id=?",
            (PUBLICATION_ID,),
        ).fetchone()[0] is None
    with pytest.raises(WorkbenchPersistenceError) as error:
        service.revalidate_publication(PUBLICATION_ID, case_id=CASE_ID, now="2026-09-01T00:00:00Z", revalidator=lambda payload: {**_facts(payload), "manifest_verified": False})
    assert error.value.code == "RETENTION_AUTHORITY_INCONSISTENT"
    verified = service.revalidate_publication(
        PUBLICATION_ID, case_id=CASE_ID, now="2026-09-01T00:00:00Z", revalidator=_facts,
    )
    assert verified["publication_verified_at"] == "2026-08-01T00:00:00Z"
    with database.connect() as connection:
        assert connection.execute(
            "SELECT publication_id FROM archive_publish_intents WHERE publication_id=?",
            (PUBLICATION_ID,),
        ).fetchone()[0] == PUBLICATION_ID


def test_eligibility_fails_closed_for_manifest_time_and_active_task(tmp_path: Path) -> None:
    database = _database(tmp_path)
    _prepare(database)
    service = CaseRetentionService(database)
    with database.connect() as connection:
        original_digest = connection.execute(
            "SELECT publication_digest FROM archive_publish_intents WHERE publication_id=?",
            (PUBLICATION_ID,),
        ).fetchone()[0]
    with database.transaction() as connection:
        connection.execute(
            "UPDATE archive_publish_intents SET publication_digest=? WHERE publication_id=?",
            ("d" * 64, PUBLICATION_ID),
        )
    result = service.evaluate_case(CASE_ID, now="2026-09-01T00:00:00Z")
    assert result["last_blocker_code"] == "RETENTION_AUTHORITY_INCONSISTENT"
    with database.transaction() as connection:
        connection.execute(
            "UPDATE archive_publish_intents SET publication_digest=? WHERE publication_id=?",
            (original_digest, PUBLICATION_ID),
        )
    TaskRecordRepository(database).create({
        "task_id": "SYNTHETIC-RETENTION-SERVICE-ACTIVE", "case_id": CASE_ID,
        "kind": "parse", "status": "queued", "stage": "queued",
    })
    result = service.evaluate_case(CASE_ID, now="2026-09-01T00:00:00Z")
    assert result["last_blocker_code"] == "RETENTION_ACTIVE_TASK"


def test_naive_and_future_durable_times_fail_closed(tmp_path: Path) -> None:
    database = _database(tmp_path)
    _prepare(database)
    service = CaseRetentionService(database)
    with database.transaction() as connection:
        connection.execute(
            "UPDATE case_retention_records SET last_meaningful_mutation_at=? WHERE case_id=?",
            ("2026-07-01T00:00:00", CASE_ID),
        )
    assert service.evaluate_case(CASE_ID, now="2026-09-01T00:00:00Z")["last_blocker_code"] == "RETENTION_TIME_INVALID"
    with database.transaction() as connection:
        connection.execute(
            "UPDATE case_retention_records SET last_meaningful_mutation_at=? WHERE case_id=?",
            ("2026-09-02T00:00:00Z", CASE_ID),
        )
    assert service.evaluate_case(CASE_ID, now="2026-09-01T00:00:00Z")["last_blocker_code"] == "RETENTION_TIME_IN_FUTURE"
