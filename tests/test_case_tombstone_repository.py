"""Synthetic cleaned-case tombstone and formal-authority preservation tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import (  # noqa: E402
    CaseDraftRepository,
    CaseShellRepository,
    CaseTombstoneRepository,
    CleanupRunRepository,
    CaseRetentionRepository,
    EditLeaseRepository,
    FormalWordArtifactRepository,
    SourceRecordRepository,
    TaskRecordRepository,
    WorkbenchDatabase,
    database_path_for_deployment,
)
from app.services.case_lifecycle_service import CaseLifecycleService  # noqa: E402
from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402

CASE_ID = "SYNTHETIC-CASE-TOMBSTONE"
SOURCE_ID = "SYNTHETIC-SOURCE-TOMBSTONE"
TASK_ID = "SYNTHETIC-TASK-TOMBSTONE"
RUN_ID = "SYNTHETIC-RUN-TOMBSTONE"
OWNER_ID = "SYNTHETIC-OWNER-TOMBSTONE"
CLAIM_TOKEN = "SYNTHETIC-CLAIM-TOMBSTONE"
PUBLICATION_ID = "SYNTHETIC-PUBLICATION-TOMBSTONE"
WORD_ID = "SYNTHETIC-WORD-TOMBSTONE"
TIME = "2026-08-02T00:00:00Z"
REPORT = {
    "title": "SYNTHETIC/TEST/InspectionReport", "document_number": "SYNTHETIC-DOC-001",
    "introduction": {"entrust_unit": "SYNTHETIC-UNIT", "entrust_persons": [], "entrust_time": "",
                     "case_summary": "SYNTHETIC", "evidence_list": [], "inspection_requirement": "",
                     "inspection_time_range": "", "inspectors": [], "inspection_place": "SYNTHETIC-PLACE"},
    "inspection": {"method": "SYNTHETIC-METHOD", "hardware_device": "SYNTHETIC-HARDWARE",
                    "software_tools": [], "process_steps": [], "result": {
                        "evidence_number": "", "software_name": "SYNTHETIC-TOOL",
                        "software_version": "1", "data_summary": "SYNTHETIC",
                        "rar_filename": "SYNTHETIC.rar", "md5_hash": "SYNTHETIC-MD5", "file_size": "0"}},
    "attachments": {"extract_list": {"columns": [], "rows": []}, "photo_ids": [], "disc_number": ""},
}


@pytest.fixture()
def database(tmp_path: Path) -> WorkbenchDatabase:
    return WorkbenchDatabase(database_path_for_deployment(tmp_path, "SYNTHETIC-DEPLOYMENT"), "SYNTHETIC-DEPLOYMENT")


def _prepare(database: WorkbenchDatabase) -> dict[str, object]:
    CaseShellRepository(database).create({
        "case_id": CASE_ID, "case_name": "SYNTHETIC/TEST/Case",
        "case_summary": "SYNTHETIC/TEST/Editable summary", "source_id": SOURCE_ID,
        "parse_task_id": TASK_ID,
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
    shells = CaseShellRepository(database)
    shells.update_lifecycle(CASE_ID, "parsing", 0)
    CaseDraftRepository(database).save({"case_id": CASE_ID, "report": REPORT, "asset_refs": [], "field_states": {}})
    with database.transaction() as connection:
        connection.execute(
            "UPDATE case_shells SET lifecycle='record_retention_expired',revision=revision+1 "
            "WHERE case_id=? AND revision=2", (CASE_ID,),
        )
        connection.execute(
            "INSERT INTO archive_attempts(attempt_id,schema_version,case_id,task_id,deployment_instance_id,source_id,"
            "input_revision,source_revision,draft_revision,report_fingerprint,status,cleanup_status,created_at,revision) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,'not_required',?,0)",
            ("SYNTHETIC-ATTEMPT-TOMBSTONE", 1, CASE_ID, TASK_ID, database.deployment_instance_id, SOURCE_ID,
             0, 0, 1, "SYNTHETIC-REPORT", "succeeded", TIME),
        )
        connection.execute(
            "INSERT INTO archive_publish_intents(intent_id,attempt_id,task_id,deployment_instance_id,case_id,source_id,"
            "source_revision,draft_revision,report_fingerprint,source_key,input_fingerprint,archive_fingerprint,manifest_id,"
            "relative_final_dir,public_manifest_json,publication_id,publication_relative_dir,publication_digest,"
            "publication_file_set_json,publication_status,fence_id,phase,publication_verified_at,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("SYNTHETIC-INTENT-TOMBSTONE", "SYNTHETIC-ATTEMPT-TOMBSTONE", TASK_ID, database.deployment_instance_id,
             CASE_ID, SOURCE_ID, 0, 1, "SYNTHETIC-REPORT", "SYNTHETIC-SOURCE-KEY", "SYNTHETIC-INPUT",
             "SYNTHETIC-ARCHIVE", "SYNTHETIC-MANIFEST", "formal", "{}", PUBLICATION_ID, "formal", "c" * 64,
             "[]", "verified", "SYNTHETIC-FENCE-TOMBSTONE", "verified", TIME, TIME, TIME),
        )
    FormalWordArtifactRepository(database).create({
        "word_artifact_id": WORD_ID, "case_id": CASE_ID, "publication_id": PUBLICATION_ID,
        "internal_relative_path": "formal/SYNTHETIC.docx", "file_digest": "a" * 64, "file_size": 12,
        "source_manifest_digest": "b" * 64, "template_identity": "legacy", "template_version": "v1",
        "generated_at": TIME, "status": "verified", "verified_at": TIME,
    })
    CaseRetentionRepository(database).upsert({
        "retention_record_id": "SYNTHETIC-RETENTION-TOMBSTONE", "case_id": CASE_ID,
        "eligibility": "eligible", "status": "processing", "last_meaningful_mutation_at": TIME,
        "latest_verified_formal_publication_at": TIME, "latest_successful_word_export_at": TIME,
        "retention_anchor_utc": TIME, "expires_at_utc": "2026-09-01T00:00:00Z",
        "policy_revision": 1, "case_revision": 3, "cleanup_revision": 0,
        "created_at": TIME, "updated_at": TIME,
    })
    runs = CleanupRunRepository(database)
    runs.create_planned({"cleanup_run_id": RUN_ID, "case_id": CASE_ID, "policy_revision": 1, "case_revision_at_plan": 3})
    claimed = runs.claim(
        RUN_ID, owner_instance_id=OWNER_ID, claim_token=CLAIM_TOKEN,
        lease_expires_at="2026-08-03T00:00:00Z", expected_case_revision=3,
        expected_policy_revision=1, now=TIME,
    )
    runs.transition(RUN_ID, from_phase="claimed", to_phase="preflighted", owner_instance_id=OWNER_ID,
                    claim_token=CLAIM_TOKEN, expected_fence_epoch=claimed["fence_epoch"],
                    expected_case_revision=3, now=TIME)
    runs.transition(RUN_ID, from_phase="preflighted", to_phase="work_files_cleaned", owner_instance_id=OWNER_ID,
                    claim_token=CLAIM_TOKEN, expected_fence_epoch=claimed["fence_epoch"],
                    expected_case_revision=3, now=TIME)
    return {"run": claimed, "fence_epoch": claimed["fence_epoch"]}


def _compact(database: WorkbenchDatabase, proof: dict[str, object], anchor: str = TIME) -> dict[str, object]:
    return CaseTombstoneRepository(database).compact_cleaned(
        CASE_ID, expected_revision=3, cleanup_run_id=RUN_ID, owner_instance_id=OWNER_ID,
        claim_token=CLAIM_TOKEN, fence_epoch=int(proof["fence_epoch"]), policy_revision=1,
        safe_display_summary="SYNTHETIC/TEST/Retained formal record", retention_anchor_utc=anchor,
        now="2026-08-02T01:00:00Z",
    )


def test_compact_keeps_tombstone_and_formal_word_after_restart(database: WorkbenchDatabase, tmp_path: Path) -> None:
    proof = _prepare(database)
    result = _compact(database, proof)
    shell = CaseShellRepository(database).get(CASE_ID)
    assert result["record_cleaned"] is True
    assert shell["record_cleaned"] is True
    assert shell["lifecycle"] == "record_cleaned"
    assert shell["source_id"] is None and shell["parse_task_id"] is None
    assert shell["report_available"] is False and shell["case_number"] is None
    assert shell["case_summary"] == "SYNTHETIC/TEST/Retained formal record"
    assert shell["retention_state"] == "completed"
    assert shell["cleanup_state"] == "records_cleaned"
    assert shell["tombstone_revision"] == 1 and shell["cleanup_revision"] == 1
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM case_drafts WHERE case_id=?", (CASE_ID,)).fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM formal_word_artifacts WHERE case_id=?", (CASE_ID,)).fetchone()[0] == 1
    assert CaseRetentionRepository(database).get_by_case(CASE_ID)["status"] == "completed"
    restarted = WorkbenchDatabase(database_path_for_deployment(tmp_path, "SYNTHETIC-DEPLOYMENT"), "SYNTHETIC-DEPLOYMENT")
    detail = CaseLifecycleService(restarted).detail(CASE_ID)
    assert detail["draft"] is None and detail["source"] is None and detail["parse_task"] is None
    assert FormalWordArtifactRepository(restarted).get_public(WORD_ID)["word_artifact_id"] == WORD_ID
    assert CleanupRunRepository(restarted).get_internal(RUN_ID)["current_phase"] == "records_cleaned"


def test_cleaned_case_rejects_edit_and_lifecycle_transition(database: WorkbenchDatabase) -> None:
    _compact(database, _prepare(database))
    with pytest.raises(WorkbenchPersistenceError, match="CASE_RECORD_CLEANED"):
        CaseDraftRepository(database).save({"case_id": CASE_ID, "report": REPORT, "asset_refs": [], "field_states": {}})
    with pytest.raises(WorkbenchPersistenceError, match="CASE_RECORD_CLEANED"):
        CaseShellRepository(database).update_lifecycle(CASE_ID, "exported", 4)
    with pytest.raises(WorkbenchPersistenceError, match="DRAFT_NOT_FOUND"):
        CaseDraftRepository(database).get(CASE_ID)


def test_authority_failure_rolls_back_draft_and_shell(database: WorkbenchDatabase) -> None:
    proof = _prepare(database)
    with database.transaction() as connection:
        connection.execute("UPDATE archive_publish_intents SET publication_verified_at=NULL WHERE publication_id=?", (PUBLICATION_ID,))
    with pytest.raises(WorkbenchPersistenceError, match="RETENTION_PUBLICATION_UNVERIFIED"):
        _compact(database, proof)
    shell = CaseShellRepository(database).get(CASE_ID)
    assert shell["record_cleaned"] is False and shell["lifecycle"] == "record_retention_expired"
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM case_drafts WHERE case_id=?", (CASE_ID,)).fetchone()[0] == 1
    assert CleanupRunRepository(database).get_internal(RUN_ID)["current_phase"] == "work_files_cleaned"


def test_active_edit_lease_blocks_tombstone(database: WorkbenchDatabase) -> None:
    proof = _prepare(database)
    EditLeaseRepository(database).acquire(
        case_id=CASE_ID, lease_id="SYNTHETIC-LEASE-TOMBSTONE", lease_token="SYNTHETIC-LEASE-TOKEN",
        identity={"identity_kind": "local_session", "session_id": "SYNTHETIC-SESSION",
                  "client_instance_id": "SYNTHETIC-CLIENT", "deployment_instance_id": database.deployment_instance_id},
    )
    with pytest.raises(WorkbenchPersistenceError, match="RETENTION_ACTIVE_LEASE"):
        _compact(database, proof)
    assert CaseShellRepository(database).get(CASE_ID)["record_cleaned"] is False


def test_naive_anchor_is_rejected_before_any_record_mutation(database: WorkbenchDatabase) -> None:
    proof = _prepare(database)
    with pytest.raises(WorkbenchPersistenceError, match="UTC_TIMESTAMP_REQUIRED"):
        _compact(database, proof, "2026-08-02T00:00:00")
    assert CaseShellRepository(database).get(CASE_ID)["record_cleaned"] is False
    assert CleanupRunRepository(database).get_internal(RUN_ID)["current_phase"] == "work_files_cleaned"


def test_case_and_draft_access_is_deployment_scoped(database: WorkbenchDatabase) -> None:
    _prepare(database)
    with database.transaction() as connection:
        connection.execute(
            "UPDATE case_shells SET deployment_instance_id=? WHERE case_id=?",
            ("SYNTHETIC-OTHER-DEPLOYMENT", CASE_ID),
        )
    with pytest.raises(WorkbenchPersistenceError, match="CASE_NOT_FOUND"):
        CaseShellRepository(database).get(CASE_ID)
    assert CaseShellRepository(database).list(0, 10) == []
    with pytest.raises(WorkbenchPersistenceError, match="CASE_NOT_FOUND"):
        CaseShellRepository(database).update_lifecycle(CASE_ID, "parsing", 3)
    with pytest.raises(WorkbenchPersistenceError, match="DRAFT_NOT_FOUND"):
        CaseDraftRepository(database).get(CASE_ID)
    with pytest.raises(WorkbenchPersistenceError, match="CASE_NOT_FOUND"):
        CaseDraftRepository(database).save({"case_id": CASE_ID, "report": REPORT, "asset_refs": [], "field_states": {}})


def test_tombstone_ignores_lease_from_another_deployment(database: WorkbenchDatabase) -> None:
    _prepare(database)
    EditLeaseRepository(database).acquire(
        case_id=CASE_ID, lease_id="SYNTHETIC-LEASE-OTHER-DEPLOYMENT", lease_token="SYNTHETIC-OTHER-LEASE-TOKEN",
        identity={"identity_kind": "local_session", "session_id": "SYNTHETIC-OTHER-SESSION",
                  "client_instance_id": "SYNTHETIC-OTHER-CLIENT", "deployment_instance_id": database.deployment_instance_id},
    )
    with database.transaction() as connection:
        connection.execute(
            "UPDATE case_shells SET deployment_instance_id=? WHERE case_id=?",
            ("SYNTHETIC-OTHER-DEPLOYMENT", CASE_ID),
        )
        CaseTombstoneRepository(database)._assert_no_active_work(connection, CASE_ID)
