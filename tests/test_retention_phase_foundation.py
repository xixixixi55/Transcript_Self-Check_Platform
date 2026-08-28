"""Slice 5A-1 清理阶段契约测试。"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import CaseShellRepository, CleanupRunRepository, WorkbenchDatabase  # noqa: E402
from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402


def _database(tmp_path: Path) -> WorkbenchDatabase:
    database = WorkbenchDatabase(tmp_path / "workbench.sqlite3", "SYNTHETIC-PHASE")
    CaseShellRepository(database).create({
        "case_id": "SYNTHETIC-CASE-PHASE",
        "case_name": "SYNTHETIC/TEST/Phase",
        "case_summary": "SYNTHETIC",
        "source_id": "SYNTHETIC-SOURCE-PHASE",
        "parse_task_id": "SYNTHETIC-TASK-PHASE",
    })
    return database


def test_partial_failure_round_trips_as_failed_and_is_recoverable(tmp_path: Path) -> None:
    database = _database(tmp_path)
    runs = CleanupRunRepository(database)
    run = runs.create_planned({
        "cleanup_run_id": "SYNTHETIC-RUN-PARTIAL",
        "case_id": "SYNTHETIC-CASE-PHASE",
        "current_phase": "partial_failure",
        "case_revision_at_plan": 0,
    })

    assert run["current_phase"] == "partial_failure"
    public = runs.get_public(run["cleanup_run_id"])
    assert public["phase"] == "partial_failure"
    assert public["status"] == "failed"

    with pytest.raises(WorkbenchPersistenceError) as error:
        runs.create_planned({
            "cleanup_run_id": "SYNTHETIC-RUN-PARTIAL-2",
            "case_id": "SYNTHETIC-CASE-PHASE",
            "current_phase": "partial_failure",
            "case_revision_at_plan": 0,
        })
    assert error.value.code == "CLEANUP_RUN_CREATE_FAILED"


def test_invalid_cleanup_phase_is_rejected_by_repository_and_schema(tmp_path: Path) -> None:
    database = _database(tmp_path)
    runs = CleanupRunRepository(database)
    with pytest.raises(WorkbenchPersistenceError) as error:
        runs.create_planned({
            "cleanup_run_id": "SYNTHETIC-RUN-INVALID",
            "case_id": "SYNTHETIC-CASE-PHASE",
            "current_phase": "SYNTHETIC-INVALID-PHASE",
            "case_revision_at_plan": 0,
        })
    assert error.value.code == "INVALID_CLEANUP_RUN"

    with database.connect() as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO case_cleanup_runs(cleanup_run_id,deployment_instance_id,case_id,"
                "policy_revision,case_revision_at_plan,current_phase,created_at,updated_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    "SYNTHETIC-RUN-INVALID-SQL", database.deployment_instance_id,
                    "SYNTHETIC-CASE-PHASE", 1, 0, "SYNTHETIC-INVALID-PHASE",
                    "2026-08-01T00:00:00Z", "2026-08-01T00:00:00Z",
                ),
            )
