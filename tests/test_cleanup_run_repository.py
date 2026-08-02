"""Synthetic T022 tests for durable cleanup run claims and recovery."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import CaseShellRepository, CleanupRunRepository, WorkbenchDatabase  # noqa: E402
from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402

NOW = "2026-08-02T00:00:00Z"


def _database(tmp_path: Path) -> WorkbenchDatabase:
    database = WorkbenchDatabase(tmp_path / "workbench.sqlite3", "SYNTHETIC-CLEANUP-T022")
    CaseShellRepository(database).create({
        "case_id": "SYNTHETIC-CASE-CLEANUP-T022",
        "case_name": "SYNTHETIC/TEST/Cleanup",
        "case_summary": "SYNTHETIC",
        "source_id": "SYNTHETIC-SOURCE-CLEANUP-T022",
        "parse_task_id": "SYNTHETIC-TASK-CLEANUP-T022",
    })
    return database


def _planned(repository: CleanupRunRepository, run_id: str = "SYNTHETIC-RUN-T022") -> dict:
    return repository.create_planned({
        "cleanup_run_id": run_id,
        "case_id": "SYNTHETIC-CASE-CLEANUP-T022",
        "policy_revision": 1,
        "case_revision_at_plan": 0,
    })


def _claim(repository: CleanupRunRepository, run_id: str, owner: str, token: str, now: str) -> dict:
    return repository.claim(
        run_id, owner_instance_id=owner, claim_token=token,
        lease_expires_at="2026-08-02T00:10:00Z", expected_case_revision=0,
        expected_policy_revision=1, now=now,
    )


def test_claim_persists_fence_and_transition_uses_owner_revision_cas(tmp_path: Path) -> None:
    runs = CleanupRunRepository(_database(tmp_path))
    _planned(runs)
    with pytest.raises(WorkbenchPersistenceError) as wrong_policy:
        runs.claim(
            "SYNTHETIC-RUN-T022", owner_instance_id="SYNTHETIC-OWNER-1",
            claim_token="SYNTHETIC-TOKEN-1", lease_expires_at="2026-08-02T00:10:00Z",
            expected_case_revision=0, expected_policy_revision=2, now=NOW,
        )
    assert wrong_policy.value.code == "CLEANUP_STALE_REQUEST"
    with pytest.raises(WorkbenchPersistenceError) as expired_lease:
        runs.claim(
            "SYNTHETIC-RUN-T022", owner_instance_id="SYNTHETIC-OWNER-1",
            claim_token="SYNTHETIC-TOKEN-1", lease_expires_at=NOW,
            expected_case_revision=0, expected_policy_revision=1, now=NOW,
        )
    assert expired_lease.value.code == "CLEANUP_STALE_REQUEST"
    claimed = _claim(runs, "SYNTHETIC-RUN-T022", "SYNTHETIC-OWNER-1", "SYNTHETIC-TOKEN-1", NOW)

    assert claimed["current_phase"] == "claimed"
    assert claimed["fence_epoch"] == 1
    assert claimed["case_revision_at_claim"] == 0
    repeated = _claim(runs, "SYNTHETIC-RUN-T022", "SYNTHETIC-OWNER-1", "SYNTHETIC-TOKEN-1", "2026-08-02T00:01:00Z")
    assert repeated["fence_epoch"] == 1
    preflighted = runs.transition(
        claimed["cleanup_run_id"], from_phase="claimed", to_phase="preflighted",
        owner_instance_id="SYNTHETIC-OWNER-1", claim_token="SYNTHETIC-TOKEN-1",
        expected_fence_epoch=1, expected_case_revision=0, expected_policy_revision=1,
        file_step_result="SYNTHETIC-PREFLIGHT-OK", now="2026-08-02T00:01:00Z",
    )
    assert preflighted["file_step_result"] == "SYNTHETIC-PREFLIGHT-OK"

    with pytest.raises(WorkbenchPersistenceError) as stale:
        runs.transition(
            claimed["cleanup_run_id"], from_phase="preflighted", to_phase="verified",
            owner_instance_id="SYNTHETIC-OWNER-1", claim_token="SYNTHETIC-TOKEN-1",
            expected_fence_epoch=2, expected_case_revision=0, expected_policy_revision=1,
            now="2026-08-02T00:02:00Z",
        )
    assert stale.value.code == "CLEANUP_STALE_REQUEST"

    succeeded = runs.transition(
        claimed["cleanup_run_id"], from_phase="preflighted", to_phase="succeeded",
        owner_instance_id="SYNTHETIC-OWNER-1", claim_token="SYNTHETIC-TOKEN-1",
        expected_fence_epoch=1, expected_case_revision=0, expected_policy_revision=1,
        result_code="SYNTHETIC-CLEANUP-SUCCEEDED", now="2026-08-02T00:03:00Z",
    )
    assert succeeded["result_code"] == "SYNTHETIC-CLEANUP-SUCCEEDED"
    assert succeeded["completed_at"] == "2026-08-02T00:03:00Z"


def test_claim_rejects_changed_current_policy_or_case_revision(tmp_path: Path) -> None:
    database = _database(tmp_path)
    runs = CleanupRunRepository(database)
    _planned(runs)
    with database.transaction() as connection:
        connection.execute(
            "UPDATE case_shells SET revision=revision+1 WHERE case_id=?",
            ("SYNTHETIC-CASE-CLEANUP-T022",),
        )
    with pytest.raises(WorkbenchPersistenceError) as changed_case:
        _claim(runs, "SYNTHETIC-RUN-T022", "SYNTHETIC-OWNER-1", "SYNTHETIC-TOKEN-1", NOW)
    assert changed_case.value.code == "CLEANUP_STALE_REQUEST"
    with database.transaction() as connection:
        connection.execute(
            "UPDATE case_shells SET revision=0 WHERE case_id=?",
            ("SYNTHETIC-CASE-CLEANUP-T022",),
        )
        connection.execute(
            "UPDATE case_retention_policies SET policy_revision=2 WHERE deployment_instance_id=?",
            (database.deployment_instance_id,),
        )
    with pytest.raises(WorkbenchPersistenceError) as changed_policy:
        _claim(runs, "SYNTHETIC-RUN-T022", "SYNTHETIC-OWNER-1", "SYNTHETIC-TOKEN-1", NOW)
    assert changed_policy.value.code == "CLEANUP_STALE_REQUEST"


def test_live_claim_conflicts_and_expired_claim_is_taken_over_with_new_fence(tmp_path: Path) -> None:
    runs = CleanupRunRepository(_database(tmp_path))
    _planned(runs)
    _claim(runs, "SYNTHETIC-RUN-T022", "SYNTHETIC-OWNER-1", "SYNTHETIC-TOKEN-1", NOW)

    with pytest.raises(WorkbenchPersistenceError) as conflict:
        _claim(runs, "SYNTHETIC-RUN-T022", "SYNTHETIC-OWNER-2", "SYNTHETIC-TOKEN-2", "2026-08-02T00:05:00Z")
    assert conflict.value.code == "CLEANUP_CONFLICT"

    taken_over = runs.claim(
        "SYNTHETIC-RUN-T022", owner_instance_id="SYNTHETIC-OWNER-2",
        claim_token="SYNTHETIC-TOKEN-2", lease_expires_at="2026-08-02T00:20:00Z",
        expected_case_revision=0, expected_policy_revision=1, now="2026-08-02T00:10:00Z",
    )
    assert taken_over["current_phase"] == "claimed"
    assert taken_over["fence_epoch"] == 2
    assert taken_over["owner_instance_id"] == "SYNTHETIC-OWNER-2"

    with pytest.raises(WorkbenchPersistenceError) as old_owner:
        runs.transition(
            "SYNTHETIC-RUN-T022", from_phase="claimed", to_phase="preflighted",
            owner_instance_id="SYNTHETIC-OWNER-1", claim_token="SYNTHETIC-TOKEN-1",
            expected_fence_epoch=1, expected_case_revision=0, expected_policy_revision=1,
            now="2026-08-02T00:11:00Z",
        )
    assert old_owner.value.code == "CLEANUP_STALE_REQUEST"
    with pytest.raises(WorkbenchPersistenceError) as expired_renewal:
        runs.renew_lease(
            "SYNTHETIC-RUN-T022", owner_instance_id="SYNTHETIC-OWNER-2",
            claim_token="SYNTHETIC-TOKEN-2", expected_fence_epoch=2,
            expected_case_revision=0, expected_policy_revision=1,
            lease_expires_at="2026-08-02T00:11:00Z", now="2026-08-02T00:11:00Z",
        )
    assert expired_renewal.value.code == "CLEANUP_STALE_REQUEST"
    renewed = runs.renew_lease(
        "SYNTHETIC-RUN-T022", owner_instance_id="SYNTHETIC-OWNER-2",
        claim_token="SYNTHETIC-TOKEN-2", expected_fence_epoch=2,
        expected_case_revision=0, expected_policy_revision=1,
        lease_expires_at="2026-08-02T00:30:00Z", now="2026-08-02T00:11:00Z",
    )
    assert renewed["lease_expires_at"] == "2026-08-02T00:30:00Z"


def test_active_unique_index_allows_new_run_only_after_terminal_result(tmp_path: Path) -> None:
    runs = CleanupRunRepository(_database(tmp_path))
    first = _planned(runs, "SYNTHETIC-RUN-T022-FIRST")
    with pytest.raises(WorkbenchPersistenceError) as duplicate:
        _planned(runs, "SYNTHETIC-RUN-T022-DUPLICATE")
    assert duplicate.value.code == "CLEANUP_RUN_CREATE_FAILED"

    claimed = _claim(runs, first["cleanup_run_id"], "SYNTHETIC-OWNER-1", "SYNTHETIC-TOKEN-1", NOW)
    runs.transition(
        claimed["cleanup_run_id"], from_phase="claimed", to_phase="failed_terminal",
        owner_instance_id="SYNTHETIC-OWNER-1", claim_token="SYNTHETIC-TOKEN-1",
        expected_fence_epoch=1, expected_case_revision=0, expected_policy_revision=1,
        error_code="SYNTHETIC-TERMINAL", now="2026-08-02T00:02:00Z",
    )
    second = _planned(runs, "SYNTHETIC-RUN-T022-SECOND")
    assert second["current_phase"] == "planned"


def test_recovery_phase_can_be_reclaimed_without_losing_file_result(tmp_path: Path) -> None:
    runs = CleanupRunRepository(_database(tmp_path))
    run = runs.create_planned({
        "cleanup_run_id": "SYNTHETIC-RUN-T022-RECOVERY",
        "case_id": "SYNTHETIC-CASE-CLEANUP-T022",
        "policy_revision": 1,
        "case_revision_at_plan": 0,
        "current_phase": "partial_failure",
        "retry_count": 1,
        "file_step_result": "SYNTHETIC-WORK-FILES-CLEANED",
    })
    reclaimed = _claim(
        runs, run["cleanup_run_id"], "SYNTHETIC-OWNER-RECOVERY", "SYNTHETIC-TOKEN-RECOVERY", NOW,
    )
    assert reclaimed["current_phase"] == "claimed"
    assert reclaimed["retry_count"] == 1
    assert reclaimed["file_step_result"] == "SYNTHETIC-WORK-FILES-CLEANED"
    assert runs.list_recoverable()[0]["cleanup_run_id"] == run["cleanup_run_id"]
