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
    WorkbenchDatabase,
    database_path_for_deployment,
)
from app.services.case_lifecycle_service import CaseLifecycleService  # noqa: E402
from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402
from case_cleanup_test_support import (  # noqa: E402
    CASE_ID,
    CLAIM_TOKEN,
    OWNER_ID,
    PUBLICATION_ID,
    REPORT,
    RUN_ID,
    TIME,
    WORD_ID,
    prepare_tombstone_case,
)


@pytest.fixture()
def database(tmp_path: Path) -> WorkbenchDatabase:
    return WorkbenchDatabase(database_path_for_deployment(tmp_path, "SYNTHETIC-DEPLOYMENT"), "SYNTHETIC-DEPLOYMENT")


def _compact(database: WorkbenchDatabase, proof: dict[str, object], anchor: str = TIME) -> dict[str, object]:
    return CaseTombstoneRepository(database).compact_cleaned(
        CASE_ID, expected_revision=3, cleanup_run_id=RUN_ID, owner_instance_id=OWNER_ID,
        claim_token=CLAIM_TOKEN, fence_epoch=int(proof["fence_epoch"]), policy_revision=1,
        safe_display_summary="SYNTHETIC/TEST/Retained formal record", retention_anchor_utc=anchor,
        now="2026-08-02T01:00:00Z",
    )


def test_compact_keeps_formal_facts_and_rejects_record_edits_after_restart(
    database: WorkbenchDatabase, tmp_path: Path,
) -> None:
    proof = prepare_tombstone_case(database)
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
    with pytest.raises(WorkbenchPersistenceError, match="CASE_RECORD_CLEANED"):
        CaseDraftRepository(database).save({
            "case_id": CASE_ID, "report": REPORT, "asset_refs": [], "field_states": {},
        })
    with pytest.raises(WorkbenchPersistenceError, match="CASE_RECORD_CLEANED"):
        CaseShellRepository(database).update_lifecycle(CASE_ID, "exported", 4)
    with pytest.raises(WorkbenchPersistenceError, match="DRAFT_NOT_FOUND"):
        CaseDraftRepository(database).get(CASE_ID)
    restarted = WorkbenchDatabase(database_path_for_deployment(tmp_path, "SYNTHETIC-DEPLOYMENT"), "SYNTHETIC-DEPLOYMENT")
    detail = CaseLifecycleService(restarted).detail(CASE_ID)
    assert detail["draft"] is None and detail["source"] is None and detail["parse_task"] is None
    assert FormalWordArtifactRepository(restarted).get_public(WORD_ID)["word_artifact_id"] == WORD_ID
    assert CleanupRunRepository(restarted).get_internal(RUN_ID)["current_phase"] == "records_cleaned"
def test_authority_failure_rolls_back_draft_and_shell(database: WorkbenchDatabase) -> None:
    proof = prepare_tombstone_case(database)
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
    proof = prepare_tombstone_case(database)
    EditLeaseRepository(database).acquire(
        case_id=CASE_ID, lease_id="SYNTHETIC-LEASE-TOMBSTONE", lease_token="SYNTHETIC-LEASE-TOKEN",
        identity={"identity_kind": "local_session", "session_id": "SYNTHETIC-SESSION",
                  "client_instance_id": "SYNTHETIC-CLIENT", "deployment_instance_id": database.deployment_instance_id},
    )
    with pytest.raises(WorkbenchPersistenceError, match="RETENTION_ACTIVE_LEASE"):
        _compact(database, proof)
    assert CaseShellRepository(database).get(CASE_ID)["record_cleaned"] is False


def test_naive_anchor_is_rejected_before_any_record_mutation(database: WorkbenchDatabase) -> None:
    proof = prepare_tombstone_case(database)
    with pytest.raises(WorkbenchPersistenceError, match="UTC_TIMESTAMP_REQUIRED"):
        _compact(database, proof, "2026-08-02T00:00:00")
    assert CaseShellRepository(database).get(CASE_ID)["record_cleaned"] is False
    assert CleanupRunRepository(database).get_internal(RUN_ID)["current_phase"] == "work_files_cleaned"


def test_case_draft_and_active_work_are_deployment_scoped(database: WorkbenchDatabase) -> None:
    prepare_tombstone_case(database)
    EditLeaseRepository(database).acquire(
        case_id=CASE_ID,
        lease_id="SYNTHETIC-LEASE-OTHER-DEPLOYMENT",
        lease_token="SYNTHETIC-OTHER-LEASE-TOKEN",
        identity={
            "identity_kind": "local_session",
            "session_id": "SYNTHETIC-OTHER-SESSION",
            "client_instance_id": "SYNTHETIC-OTHER-CLIENT",
            "deployment_instance_id": database.deployment_instance_id,
        },
    )
    with database.transaction() as connection:
        connection.execute(
            "UPDATE case_shells SET deployment_instance_id=? WHERE case_id=?",
            ("SYNTHETIC-OTHER-DEPLOYMENT", CASE_ID),
        )
        CaseTombstoneRepository(database)._assert_no_active_work(connection, CASE_ID)
    with pytest.raises(WorkbenchPersistenceError, match="CASE_NOT_FOUND"):
        CaseShellRepository(database).get(CASE_ID)
    assert CaseShellRepository(database).list(0, 10) == []
    with pytest.raises(WorkbenchPersistenceError, match="CASE_NOT_FOUND"):
        CaseShellRepository(database).update_lifecycle(CASE_ID, "parsing", 3)
    with pytest.raises(WorkbenchPersistenceError, match="DRAFT_NOT_FOUND"):
        CaseDraftRepository(database).get(CASE_ID)
    with pytest.raises(WorkbenchPersistenceError, match="CASE_NOT_FOUND"):
        CaseDraftRepository(database).save({
            "case_id": CASE_ID, "report": REPORT, "asset_refs": [], "field_states": {},
        })
