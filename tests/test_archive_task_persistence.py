"""T013 使用合成案件数据的任务持久化测试。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import (  # noqa: E402
    ArchiveTaskRepository,
    CaseShellRepository,
    ResourceSnapshotRepository,
    TaskRecordRepository,
    WorkbenchDatabase,
    database_path_for_deployment,
)
from app.repository.workbench.workbench_errors import RevisionConflictError, WorkbenchPersistenceError  # noqa: E402

CASE_ID = "SYNTHETIC-T013-CASE"
BASE = "2026-07-30T01:00:00+00:00"


@pytest.fixture()
def database(tmp_path: Path) -> WorkbenchDatabase:
    db = WorkbenchDatabase(
        database_path_for_deployment(tmp_path, "SYNTHETIC-T013"), "SYNTHETIC-T013"
    )
    CaseShellRepository(db).create({
        "case_id": CASE_ID, "case_name": "SYNTHETIC/TEST/T013",
        "case_summary": "SYNTHETIC/TEST", "source_id": "SYNTHETIC-SOURCE",
        "parse_task_id": "SYNTHETIC-PARSE",
    })
    return db


def create_task(repository: ArchiveTaskRepository, task_id: str = "SYNTHETIC-ARCHIVE-1"):
    return repository.create({
        "task_id": task_id, "case_id": CASE_ID, "stage": "queued",
        "created_at": BASE, "updated_at": BASE,
    })


def test_round_trip_restart_history_and_current_selection(database: WorkbenchDatabase) -> None:
    repository = ArchiveTaskRepository(database)
    first = create_task(repository)
    running = repository.update_state(first["task_id"], {
        "status": "running", "stage": "winrar", "started_at": BASE,
        "worker_state": "owned_running",
    }, first["revision"])
    recovering = repository.update_state(running["task_id"], {
        "worker_state": "recovering",
    }, running["revision"])
    assert recovering["worker_state"] == "recovering"
    snapshot = ResourceSnapshotRepository(database).persist(recovering["task_id"], {
        "observed_at": "2026-07-30T01:00:20+00:00",
        "output_bytes": 11_200_000_000, "output_volume_count": 3,
    }, recovering["revision"])
    assert snapshot["percent"] == 30
    assert snapshot["last_output_change_at"] == "2026-07-30T01:00:20+00:00"
    done = repository.update_state(snapshot["task_id"], {
        "status": "succeeded", "stage": "completed",
        "finished_at": "2026-07-30T01:01:00+00:00",
    }, snapshot["revision"])
    second = create_task(repository, "SYNTHETIC-ARCHIVE-2")
    reopened = ArchiveTaskRepository(
        WorkbenchDatabase(database.database_path, "SYNTHETIC-T013")
    )
    assert reopened.get_current_or_recent(CASE_ID)["task_id"] == second["task_id"]
    assert {task["task_id"] for task in reopened.get_history(CASE_ID)} == {
        done["task_id"], second["task_id"],
    }
    cancelled = reopened.update_state(second["task_id"], {
        "status": "cancelled", "finished_at": "2026-07-30T01:02:00+00:00",
    }, second["revision"])
    assert reopened.get_current_or_recent(CASE_ID)["task_id"] == cancelled["task_id"]


def test_throttle_material_change_and_stale_revision(database: WorkbenchDatabase) -> None:
    repository = ArchiveTaskRepository(database)
    queued = create_task(repository)
    running = repository.update_state(queued["task_id"], {
        "status": "running", "stage": "winrar", "worker_state": "owned_running",
        "updated_at": BASE,
    }, queued["revision"])
    snapshots = ResourceSnapshotRepository(database, interval_seconds=15)
    throttled = snapshots.persist(running["task_id"], {
        "observed_at": "2026-07-30T01:00:05+00:00",
    }, running["revision"])
    assert throttled["revision"] == running["revision"]
    changed = snapshots.persist(running["task_id"], {
        "observed_at": "2026-07-30T01:00:06+00:00", "output_bytes": 1,
    }, running["revision"])
    assert changed["revision"] == running["revision"] + 1
    with pytest.raises(RevisionConflictError):
        snapshots.persist(running["task_id"], {
            "observed_at": "2026-07-30T01:00:30+00:00",
        }, running["revision"])
    heartbeat = snapshots.persist(changed["task_id"], {
        "observed_at": "2026-07-30T01:00:30+00:00", "output_bytes": 1,
    }, changed["revision"])
    assert heartbeat["last_heartbeat_at"] == "2026-07-30T01:00:30+00:00"


@pytest.mark.parametrize("status", ["succeeded", "failed_retryable", "cancelled"])
def test_terminal_task_cannot_be_reopened_by_heartbeat(
    database: WorkbenchDatabase, status: str
) -> None:
    repository = ArchiveTaskRepository(database)
    queued = create_task(repository)
    running = repository.update_state(queued["task_id"], {
        "status": "running", "stage": "winrar",
    }, queued["revision"])
    if status == "cancelled":
        running = repository.update_state(running["task_id"], {
            "status": "cancelling",
        }, running["revision"])
    terminal_stage = "completed" if status == "succeeded" else "winrar"
    terminal = repository.update_state(running["task_id"], {
        "status": status, "stage": terminal_stage,
    }, running["revision"])
    with pytest.raises(WorkbenchPersistenceError, match="ARCHIVE_ACTIVITY_NOT_WRITABLE"):
        ResourceSnapshotRepository(database).persist(terminal["task_id"], {
            "observed_at": "2026-07-30T01:03:00+00:00", "output_bytes": 99,
        }, terminal["revision"])


def test_restart_projection_and_legacy_defaults(database: WorkbenchDatabase) -> None:
    repository = ArchiveTaskRepository(database)
    queued = create_task(repository)
    running = repository.update_state(queued["task_id"], {
        "status": "running", "stage": "winrar", "worker_state": "owned_running",
    }, queued["revision"])
    recovered = repository.recover_after_restart()
    assert recovered[0]["status"] == "interrupted"
    assert recovered[0]["worker_state"] == "waiting_reclaim"
    with database.transaction() as connection:
        connection.execute(
            "UPDATE task_records SET status='running',worker_state=NULL,"
            "progress_kind=NULL,allowed_actions_json='[]' WHERE task_id=?",
            (running["task_id"],),
        )
    legacy = TaskRecordRepository(database).get(running["task_id"])
    assert legacy["worker_state"] == "waiting_reclaim"


def test_safe_card_summary_and_exact_winrar_milestone(database: WorkbenchDatabase) -> None:
    repository = ArchiveTaskRepository(database)
    queued = create_task(repository)
    running = repository.update_state(queued["task_id"], {
        "status": "running", "stage": "winrar",
        "process_binding": {"process_tree_id": "SYNTHETIC-WORKER"},
    }, queued["revision"])
    with pytest.raises(WorkbenchPersistenceError, match="INVALID_TASK_PROGRESS"):
        repository.update_state(running["task_id"], {"percent": 31}, running["revision"])
    failed = repository.update_state(running["task_id"], {
        "status": "failed_retryable",
        "error_summary": "C:\\Users\\TEST\\secret.rar\nTraceback\n at worker.py:42",
    }, running["revision"])
    summary = repository.get_card_summary(CASE_ID)
    assert summary["error_summary"] == "[local path redacted]"
    serialized = repr(summary)
    assert "SYNTHETIC-WORKER" not in serialized
    assert "Users" not in serialized
    assert set(summary) == {
        "task_id", "case_id", "status", "progress_kind", "stage", "stage_label",
        "stage_index", "stage_count", "percent", "started_at", "updated_at",
        "finished_at", "last_heartbeat_at", "output_bytes", "output_volume_count",
        "last_output_change_at", "worker_state", "allowed_actions", "error_summary",
    }
    assert failed["allowed_actions"] == ["view_details", "retry"]
