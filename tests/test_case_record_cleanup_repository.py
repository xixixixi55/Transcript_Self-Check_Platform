"""白名单、来源墓碑和快照清理的合成数据测试。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import (  # noqa: E402
    AssetReferenceRepository,
    CaseShellRepository,
    CaseTombstoneRepository,
    CleanupRunRepository,
    SourceRecordRepository,
    TaskRecordRepository,
    WorkbenchDatabase,
    database_path_for_deployment,
)
from app.repository.workbench.workbench_errors import WorkbenchPersistenceError  # noqa: E402
from case_cleanup_test_support import (  # noqa: E402
    CASE_ID, CLAIM_TOKEN, OWNER_ID, PUBLICATION_ID, RUN_ID, SOURCE_ID, TASK_ID, TIME,
    prepare_tombstone_case,
)

EXTRA_TASK = "SYNTHETIC-TASK-WORK-CLEANUP"
EXTRA_SOURCE = "SYNTHETIC-SOURCE-ORPHAN"
SNAPSHOT_ID = "SYNTHETIC-SNAPSHOT-WORK-CLEANUP"
CONTEXT_ID = "SYNTHETIC-CONTEXT-WORK-CLEANUP"
PLAN_ID = "SYNTHETIC-PLAN-WORK-CLEANUP"
WORK_ASSET_ID = "SYNTHETIC-WORK-ASSET-CLEANUP"
FORMAL_ASSET_ID = "SYNTHETIC-FORMAL-ASSET-CLEANUP"
DEPLOYMENT = "SYNTHETIC-DEPLOYMENT"


@pytest.fixture()
def database(tmp_path: Path) -> WorkbenchDatabase:
    return WorkbenchDatabase(database_path_for_deployment(tmp_path, DEPLOYMENT), DEPLOYMENT)


def _prepare_work_records(
    database: WorkbenchDatabase, *, snapshot_status: str = "cleaned",
    active_context: bool = False, unknown_asset: bool = False,
) -> tuple[dict[str, object], str]:
    proof = prepare_tombstone_case(database)
    TaskRecordRepository(database).create({
        "task_id": EXTRA_TASK, "case_id": CASE_ID, "kind": "parse",
        "status": "succeeded", "stage": "completed",
    })
    SourceRecordRepository(database).create({
        "source_id": EXTRA_SOURCE, "case_id": CASE_ID, "task_id": EXTRA_TASK,
        "source_type": "report_directory", "internal_path": "SYNTHETIC/TEST/orphan",
        "allowed_root": "SYNTHETIC/TEST", "allowed_root_id": "SYNTHETIC-ORPHAN-ROOT",
        "fingerprint": "SYNTHETIC-ORPHAN-FINGERPRINT", "metadata": {},
    })
    AssetReferenceRepository(database).create({
        "asset_id": "SYNTHETIC-ASSET-REFERENCE-CLEANUP", "case_id": CASE_ID,
        "asset_kind": "staging", "fingerprint": "SYNTHETIC-REFERENCE-FP",
        "metadata": {},
    })
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO archive_plans VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (PLAN_ID, 1, CASE_ID, 1, 1, 1, "{}", "[]", TIME, TIME, 1),
        )
        connection.execute(
            "INSERT INTO archive_context_bindings(context_hash,attempt_id,case_id,active,created_at,source_id,"
            "source_revision,draft_revision,report_fingerprint,context_kind,expires_at,consumed_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (CONTEXT_ID, "SYNTHETIC-ATTEMPT-TOMBSTONE", CASE_ID, int(active_context), TIME, SOURCE_ID,
             0, 1, "SYNTHETIC-REPORT", "workbench", None, None),
        )
        connection.execute(
            "INSERT INTO archive_input_snapshots(snapshot_id,task_id,attempt_id,deployment_instance_id,case_id,source_id,"
            "source_revision,draft_revision,source_root_id,snapshot_root_id,snapshot_locator,manifest_json,input_fingerprint,"
            "status,marker_token,created_at,sealed_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (SNAPSHOT_ID, TASK_ID, "SYNTHETIC-ATTEMPT-TOMBSTONE", DEPLOYMENT, CASE_ID, SOURCE_ID, 0, 1,
             "SYNTHETIC-ROOT", "SYNTHETIC-SNAPSHOT-ROOT", "snapshot/SYNTHETIC", "{}", "SYNTHETIC-SNAPSHOT-FP",
             snapshot_status, "SYNTHETIC-SNAPSHOT-MARKER", TIME, TIME, TIME),
        )
        connection.execute(
            "UPDATE archive_attempts SET input_snapshot_id=?,input_snapshot_root_id=?,input_snapshot_locator=?,"
            "input_snapshot_fingerprint=?,input_snapshot_status=? WHERE attempt_id=?",
            (SNAPSHOT_ID, "SYNTHETIC-SNAPSHOT-ROOT", "snapshot/SYNTHETIC", "SYNTHETIC-SNAPSHOT-FP",
             snapshot_status, "SYNTHETIC-ATTEMPT-TOMBSTONE"),
        )
        connection.execute(
            "INSERT INTO archive_assets VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (WORK_ASSET_ID, 1, CASE_ID, None if unknown_asset else EXTRA_TASK,
             None if unknown_asset else PLAN_ID, "staging", "temporary", "staging/SYNTHETIC.work", "{}", TIME, TIME, 1),
        )
        connection.execute(
            "INSERT INTO archive_assets VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (FORMAL_ASSET_ID, 1, CASE_ID, TASK_ID, None, "rar_volume", "published", "formal/SYNTHETIC.rar",
             "{}", TIME, TIME, 1),
        )
    receipt = json.dumps({
        "version": 1, "ownership_verified": True,
        "deleted_snapshot_ids": [SNAPSHOT_ID],
        "deleted_asset_ids": [WORK_ASSET_ID],
    })
    return proof, receipt


def _compact(database: WorkbenchDatabase, proof: dict[str, object], receipt: str | None) -> None:
    CaseTombstoneRepository(database).compact_cleaned(
        CASE_ID, expected_revision=3, cleanup_run_id=RUN_ID, owner_instance_id=OWNER_ID,
        claim_token=CLAIM_TOKEN, fence_epoch=int(proof["fence_epoch"]), policy_revision=1,
        safe_display_summary="SYNTHETIC/TEST/Retained formal record", retention_anchor_utc=TIME,
        file_step_result=receipt, now="2026-08-02T01:00:00Z",
    )


def test_whitelist_cleanup_preserves_formal_facts_and_tombstones_source(database: WorkbenchDatabase) -> None:
    proof, receipt = _prepare_work_records(database)
    _compact(database, proof, receipt)
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM archive_input_snapshots").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM archive_context_bindings").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM case_drafts").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM asset_references").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM archive_assets WHERE asset_id=?", (WORK_ASSET_ID,)).fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM archive_assets WHERE asset_id=?", (FORMAL_ASSET_ID,)).fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM archive_plans").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM task_records WHERE task_id=?", (EXTRA_TASK,)).fetchone()[0] == 0
        task = connection.execute("SELECT counters_json,process_binding_json,publication_id FROM task_records WHERE task_id=?", (TASK_ID,)).fetchone()
        assert task[0] == "{}" and task[1] is None and task[2] is None
        source = connection.execute("SELECT * FROM source_records WHERE source_id=?", (SOURCE_ID,)).fetchone()
        assert source["tombstone_state"] == "tombstoned"
        assert source["internal_path"] is None and source["allowed_root"] is None and source["task_id"] is None
        assert connection.execute("SELECT COUNT(*) FROM source_records WHERE source_id=?", (EXTRA_SOURCE,)).fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM archive_publish_intents WHERE publication_id=?", (PUBLICATION_ID,)).fetchone()[0] == 1
        assert connection.execute("PRAGMA foreign_key_check").fetchone() is None
    assert CaseShellRepository(database).get(CASE_ID)["record_cleaned"] is True
    assert CleanupRunRepository(database).get_internal(RUN_ID)["current_phase"] == "records_cleaned"


def test_snapshot_active_blocks_before_any_record_mutation(database: WorkbenchDatabase) -> None:
    proof, receipt = _prepare_work_records(database, snapshot_status="sealed")
    with pytest.raises(WorkbenchPersistenceError, match="RETENTION_SNAPSHOT_ACTIVE"):
        _compact(database, proof, receipt)
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM archive_input_snapshots").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM case_drafts").fetchone()[0] == 1
    assert CaseShellRepository(database).get(CASE_ID)["record_cleaned"] is False


def test_snapshot_recovery_and_missing_file_receipt_fail_closed(database: WorkbenchDatabase) -> None:
    proof, receipt = _prepare_work_records(database, active_context=True)
    with pytest.raises(WorkbenchPersistenceError, match="RETENTION_SNAPSHOT_RECOVERY_REFERENCED"):
        _compact(database, proof, receipt)


def test_missing_file_receipt_fail_closed(database: WorkbenchDatabase) -> None:
    proof, _ = _prepare_work_records(database)
    with pytest.raises(WorkbenchPersistenceError, match="RETENTION_SNAPSHOT_OWNERSHIP_UNKNOWN"):
        _compact(database, proof, None)


def test_unknown_work_asset_ownership_rolls_back(database: WorkbenchDatabase) -> None:
    proof, receipt = _prepare_work_records(database, unknown_asset=True)
    with pytest.raises(WorkbenchPersistenceError, match="RETENTION_OWNERSHIP_UNKNOWN"):
        _compact(database, proof, receipt)
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM archive_assets WHERE asset_id=?", (WORK_ASSET_ID,)).fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM case_drafts WHERE case_id=?", (CASE_ID,)).fetchone()[0] == 1
