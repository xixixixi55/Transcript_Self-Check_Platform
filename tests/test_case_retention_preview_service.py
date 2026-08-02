"""Synthetic deterministic and safe-projection tests for task 3.2."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import CaseShellRepository, TaskRecordRepository, WorkbenchDatabase  # noqa: E402
from app.services.case_retention_preview_service import CaseRetentionPreviewService  # noqa: E402


def _database(tmp_path: Path) -> WorkbenchDatabase:
    return WorkbenchDatabase(tmp_path / "workbench.sqlite3", "SYNTHETIC-RETENTION-PREVIEW")


def _cases(database: WorkbenchDatabase) -> None:
    CaseShellRepository(database).create({
        "case_id": "SYNTHETIC-PREVIEW-CANDIDATE", "case_name": "SYNTHETIC/TEST/Candidate",
        "case_summary": "SYNTHETIC", "source_id": "SYNTHETIC-PREVIEW-SOURCE-1",
        "parse_task_id": "SYNTHETIC-PREVIEW-PARSE-1",
    })
    CaseShellRepository(database).create({
        "case_id": "SYNTHETIC-PREVIEW-BLOCKED", "case_name": "SYNTHETIC/TEST/Blocked",
        "case_summary": "SYNTHETIC", "source_id": "SYNTHETIC-PREVIEW-SOURCE-2",
        "parse_task_id": "SYNTHETIC-PREVIEW-PARSE-2",
    })
    TaskRecordRepository(database).create({
        "task_id": "SYNTHETIC-PREVIEW-ACTIVE-TASK", "case_id": "SYNTHETIC-PREVIEW-CANDIDATE",
        "kind": "parse", "status": "queued", "stage": "queued",
    })


def test_preview_is_sorted_safe_and_digest_stable(tmp_path: Path) -> None:
    database = _database(tmp_path)
    _cases(database)
    service = CaseRetentionPreviewService(database)
    service.retention.evaluate_case = lambda case_id, now: {
        "case_id": case_id,
        "eligibility": "eligible" if case_id.endswith("CANDIDATE") else "unknown",
        "status": "eligible" if case_id.endswith("CANDIDATE") else "unknown",
        "last_blocker_code": None if case_id.endswith("CANDIDATE") else "RETENTION_PUBLICATION_MISSING",
        "retention_anchor_utc": "2026-07-10T00:00:00Z" if case_id.endswith("CANDIDATE") else None,
        "expires_at_utc": "2026-08-09T00:00:00Z" if case_id.endswith("CANDIDATE") else None,
        "case_revision": 0,
    }
    first = service.preview(now="2026-09-01T00:00:00Z")
    second = service.preview(now="2026-09-01T00:00:00Z")
    assert [item["case_id"] for item in first["items"]] == [
        "SYNTHETIC-PREVIEW-BLOCKED", "SYNTHETIC-PREVIEW-CANDIDATE",
    ]
    candidate = next(item for item in first["items"] if item["case_id"].endswith("CANDIDATE"))
    blocked = next(item for item in first["items"] if item["case_id"].endswith("BLOCKED"))
    assert candidate["state"] == "candidate"
    assert candidate["has_running_task"] is True
    assert candidate["has_conflict"] is True
    assert blocked["state"] == "blocked"
    assert blocked["blocker_code"] == "RETENTION_PUBLICATION_MISSING"
    assert first["preview_digest"] == second["preview_digest"]
    assert first["items"] == second["items"]
    assert len(first["preview_digest"]) == 64
    assert all(len(item["digest"]) == 64 for item in first["items"])

    serialized = json.dumps(first, ensure_ascii=False, sort_keys=True)
    for forbidden in (
        "internal_relative_path", "relative_final_dir", "archive_input_snapshots",
        "owner_instance_id", "claim_token", "lease_expires_at", "fence_epoch",
        "attempt_id", "context_hash", "SYNTHETIC/TEST/formal",
    ):
        assert forbidden not in serialized
    assert first["policy"] == {
        "mode": "disabled", "retention_days": 30, "scan_interval_seconds": 86400,
        "batch_size": 20, "policy_revision": 1, "activated_at": None,
        "updated_at": first["policy"]["updated_at"],
    }
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM case_cleanup_runs").fetchone()[0] == 0
