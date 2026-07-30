"""Phase 1A persistence tests using synthetic data and temporary databases."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import (  # noqa: E402
    AssetReferenceRepository,
    AuditEventRepository,
    CaseDraftRepository,
    CaseShellRepository,
    EditLeaseRepository,
    SharedDefaultsRepository,
    SourceRecordRepository,
    TaskRecordRepository,
    WorkbenchDatabase,
    database_path_for_deployment,
    default_workbench_data_root,
)
from app.repository.case_workflow_repository import CaseWorkflowRepository  # noqa: E402
from app.repository.workbench_errors import (  # noqa: E402
    ForbiddenPayloadError,
    LeaseConflictError,
    RevisionConflictError,
    SchemaIncompatibleError,
    WorkbenchPersistenceError,
)

CASE_ID = "SYNTHETIC-CASE-001"
SOURCE_ID = "SYNTHETIC-SOURCE-001"
TASK_ID = "SYNTHETIC-TASK-001"
IDENTITY = {
    "identity_kind": "local_session",
    "client_instance_id": "SYNTHETIC-CLIENT-001",
    "session_id": "SYNTHETIC-SESSION-001",
    "deployment_instance_id": "SYNTHETIC-DEPLOYMENT",
}
REPORT = {
    "title": "SYNTHETIC/TEST/InspectionReport",
    "document_number": "SYNTHETIC-DOC-001",
    "introduction": {
        "entrust_unit": "SYNTHETIC-UNIT", "entrust_persons": [], "entrust_time": "",
        "case_summary": "SYNTHETIC", "evidence_list": [], "inspection_requirement": "",
        "inspection_time_range": "", "inspectors": [], "inspection_place": "SYNTHETIC-PLACE",
    },
    "inspection": {
        "method": "SYNTHETIC-METHOD", "hardware_device": "SYNTHETIC-HARDWARE",
        "software_tools": [], "process_steps": [],
        "result": {
            "evidence_number": "", "software_name": "SYNTHETIC-TOOL", "software_version": "1",
            "data_summary": "SYNTHETIC", "rar_filename": "SYNTHETIC.rar",
            "md5_hash": "SYNTHETIC-MD5", "file_size": "0",
        },
    },
    "attachments": {
        "extract_list": {"columns": [], "rows": []}, "photo_ids": [], "disc_number": "",
    },
}


@pytest.fixture()
def database(tmp_path: Path) -> WorkbenchDatabase:
    return WorkbenchDatabase(
        database_path_for_deployment(tmp_path, "SYNTHETIC-DEPLOYMENT"),
        "SYNTHETIC-DEPLOYMENT",
    )


def create_shell(database: WorkbenchDatabase) -> dict:
    return CaseShellRepository(database).create({
        "case_id": CASE_ID,
        "case_name": "SYNTHETIC/TEST/Case",
        "case_summary": "SYNTHETIC/TEST/Summary",
        "source_id": SOURCE_ID,
        "parse_task_id": TASK_ID,
    })


def create_parse_task(database: WorkbenchDatabase, status: str = "queued") -> dict:
    return TaskRecordRepository(database).create({
        "task_id": TASK_ID, "case_id": CASE_ID, "kind": "parse", "status": status,
        "stage": "parse", "counters": {},
    })


def test_empty_init_upgrade_repeat_and_deployment_isolation(tmp_path: Path) -> None:
    first_path = database_path_for_deployment(tmp_path, "SYNTHETIC-A")
    second_path = database_path_for_deployment(tmp_path, "SYNTHETIC-B")
    first = WorkbenchDatabase(first_path, "SYNTHETIC-A")
    assert first.schema_version() == 6
    assert {"schema_migrations", "case_shells", "case_drafts", "source_records", "shared_defaults", "task_records", "edit_leases", "asset_references", "audit_events", "archive_attempts", "archive_context_bindings", "archive_publish_intents", "archive_publish_fences", "archive_plans", "archive_assets"}.issubset(first.table_names())
    WorkbenchDatabase(first_path, "SYNTHETIC-A")
    second = WorkbenchDatabase(second_path, "SYNTHETIC-B")
    assert first_path != second_path
    assert second.schema_version() == 6


def test_default_database_root_is_application_data_not_repository_root() -> None:
    root = default_workbench_data_root()
    path = database_path_for_deployment(None, "SYNTHETIC-DEFAULT")
    assert path.parent.parent.parent == root
    assert path.name == "workbench.sqlite3"
    assert Path.cwd() not in path.parents


def test_sqlite_pragmas_and_atomic_migration_failure(tmp_path: Path) -> None:
    path = database_path_for_deployment(tmp_path, "SYNTHETIC-PRAGMAS")
    database = WorkbenchDatabase(path, "SYNTHETIC-PRAGMAS")
    with database.connect() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"

    failed_path = database_path_for_deployment(tmp_path, "SYNTHETIC-MIGRATION-FAIL")
    failed_path.parent.mkdir(parents=True)
    with sqlite3.connect(failed_path) as connection:
        connection.execute("CREATE TABLE case_shells (sentinel TEXT NOT NULL)")
    with pytest.raises(WorkbenchPersistenceError) as error:
        WorkbenchDatabase(failed_path, "SYNTHETIC-MIGRATION-FAIL")
    assert error.value.code == "SQLITE_CORRUPTED"
    with sqlite3.connect(failed_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM case_shells").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE name = 'schema_migrations'").fetchone()[0] == 0

    wal_path = database_path_for_deployment(tmp_path, "SYNTHETIC-WAL")
    wal_path.parent.mkdir(parents=True)
    with sqlite3.connect(wal_path) as connection:
        assert connection.execute("PRAGMA journal_mode = WAL").fetchone()[0] == "wal"
    with pytest.raises(SchemaIncompatibleError):
        WorkbenchDatabase(wal_path, "SYNTHETIC-WAL")


def test_transaction_rolls_back_on_failure(database: WorkbenchDatabase) -> None:
    with pytest.raises(RuntimeError):
        with database.transaction() as connection:
            connection.execute(
                "INSERT INTO audit_events(event_id, event_type, deployment_instance_id, client_instance_id, session_id, identity_kind, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("SYNTHETIC-EVENT-001", "TEST", "SYNTHETIC-DEPLOYMENT", "SYNTHETIC-CLIENT-001", "SYNTHETIC-SESSION-001", "local_session", "{}", "SYNTHETIC-TIME"),
            )
            raise RuntimeError("SYNTHETIC_ROLLBACK")
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0] == 0


def test_shared_defaults_migration_initializes_fresh_singleton(database: WorkbenchDatabase) -> None:
    result = SharedDefaultsRepository(database).decide_migration("ignored")
    assert result["migration_decision"] == "ignored"


def test_case_shell_exists_before_parse_and_failed_parse_has_no_draft(database: WorkbenchDatabase) -> None:
    shell = create_shell(database)
    assert shell["report_available"] is False
    task = create_parse_task(database)
    with pytest.raises(WorkbenchPersistenceError) as queued_draft_error:
        CaseDraftRepository(database).save({"case_id": CASE_ID, "report": REPORT, "asset_refs": [], "field_states": {}})
    parsing = CaseShellRepository(database).update_lifecycle(CASE_ID, "parsing", 0)
    with pytest.raises(WorkbenchPersistenceError) as direct_review_error:
        CaseShellRepository(database).update_lifecycle(CASE_ID, "review_ready", parsing["revision"])
    assert direct_review_error.value.code == "DRAFT_NOT_REVIEWABLE"
    assert task["status"] == "queued"
    assert queued_draft_error.value.code == "DRAFT_NOT_REVIEWABLE"
    failed = CaseShellRepository(database).update_lifecycle(CASE_ID, "parse_failed_retryable", parsing["revision"])
    assert failed["report_available"] is False
    with pytest.raises(WorkbenchPersistenceError) as draft_error:
        CaseDraftRepository(database).save({"case_id": CASE_ID, "report": REPORT, "asset_refs": [], "field_states": {}})
    assert draft_error.value.code == "DRAFT_NOT_REVIEWABLE"
    with pytest.raises(WorkbenchPersistenceError) as error:
        CaseDraftRepository(database).get(CASE_ID)
    assert error.value.code == "DRAFT_NOT_FOUND"


def test_case_and_asset_ids_reject_path_shaped_values(database: WorkbenchDatabase) -> None:
    with pytest.raises(ForbiddenPayloadError):
        CaseShellRepository(database).create({
            "case_id": "C:\\SYNTHETIC\\case", "source_id": SOURCE_ID, "parse_task_id": TASK_ID,
        })


def test_draft_revision_conflict_does_not_overwrite(database: WorkbenchDatabase) -> None:
    create_shell(database)
    CaseShellRepository(database).update_lifecycle(CASE_ID, "parsing", 0)
    repository = CaseDraftRepository(database)
    saved = repository.save({"case_id": CASE_ID, "report": REPORT, "asset_refs": [], "field_states": {}})
    assert saved["revision"] == 1
    with pytest.raises(RevisionConflictError):
        repository.save({"case_id": CASE_ID, "report": {**REPORT, "title": "SYNTHETIC-OTHER"}, "asset_refs": [], "field_states": {}}, expected_revision=0)
    assert repository.get(CASE_ID)["report"]["title"] == REPORT["title"]


def test_stable_review_ids_preserve_legacy_report_projection(database: WorkbenchDatabase) -> None:
    create_shell(database)
    CaseShellRepository(database).update_lifecycle(CASE_ID, "parsing", 0)
    report = json.loads(json.dumps(REPORT))
    report["introduction"]["evidence_list"] = [{
        "id": "SYNTHETIC-LEGACY-EVIDENCE-1",
        "evidence_id": "SYNTHETIC-STABLE-EVIDENCE-1",
        "device_type": "phone",
        "evidence_number": "检材2",
    }]
    report["introduction"]["inspectors"] = [{
        "name": "SYNTHETIC-NAME", "unit": "SYNTHETIC-UNIT", "badge_number": "SYNTHETIC-BADGE",
    }]
    report["introduction"]["inspector_snapshots"] = [{
        "snapshot_id": "SYNTHETIC-STABLE-INSPECTOR-1",
        "inspector_id": "SYNTHETIC-INSPECTOR-1",
        "name": "SYNTHETIC-NAME", "unit": "SYNTHETIC-UNIT", "police_number": "SYNTHETIC-BADGE",
    }]

    saved = CaseDraftRepository(database).save({
        "case_id": CASE_ID, "report": report, "asset_refs": [], "field_states": {},
    })

    persisted = CaseDraftRepository(database).get(CASE_ID)["report"]
    assert saved["revision"] == 1
    assert persisted["introduction"]["evidence_list"][0]["evidence_id"] == "SYNTHETIC-STABLE-EVIDENCE-1"
    assert persisted["introduction"]["inspector_snapshots"][0]["snapshot_id"] == "SYNTHETIC-STABLE-INSPECTOR-1"
    assert persisted["introduction"]["inspectors"] == report["introduction"]["inspectors"]


def test_draft_requires_complete_legacy_report_and_opaque_archive_plan(database: WorkbenchDatabase) -> None:
    create_shell(database)
    CaseShellRepository(database).update_lifecycle(CASE_ID, "parsing", 0)
    repository = CaseDraftRepository(database)
    with pytest.raises(WorkbenchPersistenceError) as incomplete:
        repository.save({"case_id": CASE_ID, "report": {"title": "SYNTHETIC"}, "asset_refs": [], "field_states": {}})
    assert incomplete.value.code == "INVALID_LEGACY_REPORT"
    with pytest.raises(WorkbenchPersistenceError) as canonical:
        repository.save({"case_id": CASE_ID, "report": REPORT, "report_version": "canonical-v1", "asset_refs": [], "field_states": {}})
    assert canonical.value.code == "INVALID_LEGACY_REPORT"
    with pytest.raises(ForbiddenPayloadError):
        repository.save({"case_id": CASE_ID, "report": REPORT, "archive_plan_id": "C:\\SYNTHETIC\\plan", "asset_refs": [], "field_states": {}})


def test_corrupt_legacy_report_is_not_returned_as_reviewable_draft(database: WorkbenchDatabase) -> None:
    create_shell(database)
    CaseShellRepository(database).update_lifecycle(CASE_ID, "parsing", 0)
    repository = CaseDraftRepository(database)
    repository.save({"case_id": CASE_ID, "report": REPORT, "asset_refs": [], "field_states": {}})
    with database.connect() as connection:
        connection.execute(
            "UPDATE case_drafts SET report_json = ? WHERE case_id = ?",
            (json.dumps({**REPORT, "title": 7}), CASE_ID),
        )
    with pytest.raises(WorkbenchPersistenceError) as invalid:
        repository.get(CASE_ID)
    assert invalid.value.code == "INVALID_LEGACY_REPORT"


def test_forbidden_large_objects_are_rejected_and_asset_refs_are_opaque(database: WorkbenchDatabase) -> None:
    create_shell(database)
    CaseShellRepository(database).update_lifecycle(CASE_ID, "parsing", 0)
    repository = CaseDraftRepository(database)
    with pytest.raises(ForbiddenPayloadError):
        repository.save({"case_id": CASE_ID, "report": {**REPORT, "raw_html": "<html>SYNTHETIC</html>"}, "asset_refs": [], "field_states": {}})
    with pytest.raises(ForbiddenPayloadError):
        repository.save({"case_id": CASE_ID, "report": {**REPORT, "photo_data": "data:image/png;base64,SYNTHETIC"}, "asset_refs": [], "field_states": {}})
    with pytest.raises(ForbiddenPayloadError):
        repository.save({"case_id": CASE_ID, "report": {**REPORT, "path": "C:\\SYNTHETIC\\report.html"}, "asset_refs": [], "field_states": {}})
    AssetReferenceRepository(database).create({
        "asset_id": "SYNTHETIC-ASSET-001", "case_id": CASE_ID, "asset_kind": "image",
        "metadata": {"label": "SYNTHETIC/TEST"},
    })
    assert AssetReferenceRepository(database).get("SYNTHETIC-ASSET-001")["case_id"] == CASE_ID
    with pytest.raises(WorkbenchPersistenceError) as mismatched_asset:
        repository.save({
            "case_id": CASE_ID, "report": REPORT,
            "asset_refs": [{"asset_id": "SYNTHETIC-ASSET-001", "asset_kind": "source_snapshot"}],
            "field_states": {},
        })
    assert mismatched_asset.value.code == "ASSET_REFERENCE_MISMATCH"
    with pytest.raises(WorkbenchPersistenceError) as mismatched_fingerprint:
        repository.save({
            "case_id": CASE_ID, "report": REPORT,
            "asset_refs": [{"asset_id": "SYNTHETIC-ASSET-001", "asset_kind": "image", "fingerprint": "SYNTHETIC-OTHER"}],
            "field_states": {},
        })
    assert mismatched_fingerprint.value.code == "ASSET_REFERENCE_MISMATCH"
    saved = repository.save({
        "case_id": CASE_ID, "report": REPORT,
        "asset_refs": [{"asset_id": "SYNTHETIC-ASSET-001", "asset_kind": "image"}], "field_states": {},
    })
    assert saved["asset_refs"][0]["asset_id"] == "SYNTHETIC-ASSET-001"
    with pytest.raises(WorkbenchPersistenceError) as missing_asset:
        repository.save({
            "case_id": CASE_ID, "report": REPORT,
            "asset_refs": [{"asset_id": "SYNTHETIC-ASSET-MISSING", "asset_kind": "image"}], "field_states": {},
        })
    assert missing_asset.value.code == "ASSET_REFERENCE_NOT_FOUND"
    with database.connect() as connection:
        rows = connection.execute("SELECT report_json, field_states_json, asset_refs_json FROM case_drafts").fetchall()
        assert all("base64" not in json.dumps(tuple(row)).casefold() for row in rows)
        tables = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()]
        for table in tables:
            columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()]
            for column in columns:
                assert connection.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE typeof({column}) = 'blob'"
                ).fetchone()[0] == 0


def test_source_record_revalidates_without_exposing_absolute_path(database: WorkbenchDatabase, tmp_path: Path) -> None:
    create_shell(database)
    source_root = tmp_path / "SYNTHETIC-source-root"
    source_root.mkdir()
    source_file = source_root / "SYNTHETIC-report.html"
    source_file.write_text("SYNTHETIC/TEST", encoding="utf-8")
    stat = source_file.stat()
    repository = SourceRecordRepository(database)
    with pytest.raises(ForbiddenPayloadError):
        repository.create({
            "source_id": "SYNTHETIC-SOURCE-PATH", "case_id": CASE_ID, "source_type": "uploaded_file",
            "internal_path": str(source_file), "allowed_root": str(source_root),
            "allowed_root_id": "C:\\SYNTHETIC\\root",
        })
    with pytest.raises(WorkbenchPersistenceError) as unverified:
        repository.create({
            "source_id": "SYNTHETIC-SOURCE-UNVERIFIED", "case_id": CASE_ID, "source_type": "uploaded_file",
            "internal_path": str(source_file), "allowed_root": str(source_root),
            "allowed_root_id": "SYNTHETIC-ROOT-002", "fingerprint": "SYNTHETIC-FINGERPRINT-002",
            "access_status": "available",
        })
    assert unverified.value.code == "SOURCE_REVALIDATION_REQUIRED"
    public = repository.create({
        "source_id": SOURCE_ID, "case_id": CASE_ID, "source_type": "uploaded_file",
        "internal_path": str(source_file), "allowed_root": str(source_root),
        "allowed_root_id": "SYNTHETIC-ROOT-001",
        "metadata": {"size_bytes": stat.st_size, "modified_time_ns": stat.st_mtime_ns},
        "fingerprint": "SYNTHETIC-FINGERPRINT-001",
    })
    assert "internal_path" not in public
    assert public["allowed_root_id"] == "SYNTHETIC-ROOT-001"
    assert str(source_file) not in json.dumps(public)
    assert repository.revalidate(SOURCE_ID, current_fingerprint="SYNTHETIC-FINGERPRINT-001")["access_status"] == "available"
    source_file.write_text("SYNTHETIC/XXXX", encoding="utf-8")
    assert repository.revalidate(SOURCE_ID, current_fingerprint="SYNTHETIC-FINGERPRINT-CHANGED")["access_status"] == "requires_reselection"
    assert repository.revalidate(SOURCE_ID)["access_status"] == "requires_reselection"


def test_shared_defaults_are_deployment_scoped_and_migration_is_once_only(database: WorkbenchDatabase) -> None:
    repository = SharedDefaultsRepository(database)
    initial = repository.get()
    saved = repository.save({**initial, "document_number": "SYNTHETIC-DEFAULT"}, initial["revision"])
    assert saved["document_number"] == "SYNTHETIC-DEFAULT"
    with pytest.raises(RevisionConflictError):
        repository.save({"document_number": "SYNTHETIC-STALE"}, initial["revision"])
    imported = repository.decide_migration("imported", {"document_number": "SYNTHETIC-IMPORTED"})
    assert imported["migration_decision"] == "imported"
    with pytest.raises(WorkbenchPersistenceError) as error:
        repository.decide_migration("ignored")
    assert error.value.code == "DEFAULTS_MIGRATION_ALREADY_DECIDED"


def test_client_identity_audit_is_local_session_not_authenticated(database: WorkbenchDatabase) -> None:
    repository = AuditEventRepository(database)
    event = repository.record({"event_id": "SYNTHETIC-EVENT-002", "event_type": "defaults_changed", **IDENTITY, "payload": {}})
    assert event["identity_kind"] == "local_session"
    with pytest.raises(WorkbenchPersistenceError):
        repository.record({"event_id": "SYNTHETIC-EVENT-003", "event_type": "invalid", **{**IDENTITY, "identity_kind": "authenticated_user"}, "payload": {}})


def test_only_one_active_lease_and_expired_lease_can_be_taken_over(database: WorkbenchDatabase) -> None:
    create_shell(database)
    repository = EditLeaseRepository(database)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(WorkbenchPersistenceError) as naive_time:
        repository.acquire(case_id=CASE_ID, lease_id="SYNTHETIC-LEASE-NAIVE", lease_token="SYNTHETIC-TOKEN-NAIVE", identity=IDENTITY, now=datetime(2026, 1, 1))
    assert naive_time.value.code == "UTC_TIMESTAMP_REQUIRED"
    first = repository.acquire(case_id=CASE_ID, lease_id="SYNTHETIC-LEASE-001", lease_token="SYNTHETIC-TOKEN-001", identity=IDENTITY, now=start)
    with pytest.raises(LeaseConflictError):
        repository.acquire(case_id=CASE_ID, lease_id="SYNTHETIC-LEASE-002", lease_token="SYNTHETIC-TOKEN-002", identity=IDENTITY, now=start + timedelta(seconds=30))
    with pytest.raises(WorkbenchPersistenceError) as takeover_error:
        repository.acquire(case_id=CASE_ID, lease_id="SYNTHETIC-LEASE-002", lease_token="SYNTHETIC-TOKEN-002", identity=IDENTITY, now=start + timedelta(seconds=121))
    assert takeover_error.value.code == "LEASE_TAKEOVER_REQUIRED"
    second = repository.acquire(case_id=CASE_ID, lease_id="SYNTHETIC-LEASE-002", lease_token="SYNTHETIC-TOKEN-002", identity=IDENTITY, now=start + timedelta(seconds=121), force_takeover=True)
    assert first["status"] == "active"
    assert second["status"] == "active"
    assert second["takeover_of_lease_id"] == first["lease_id"]
    assert repository.get(first["lease_id"])["status"] == "expired"


def test_expired_heartbeat_persists_and_live_heartbeat_uses_revision(database: WorkbenchDatabase) -> None:
    create_shell(database)
    repository = EditLeaseRepository(database)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    lease = repository.acquire(
        case_id=CASE_ID, lease_id="SYNTHETIC-LEASE-HEARTBEAT", lease_token="SYNTHETIC-TOKEN-HEARTBEAT",
        identity=IDENTITY, now=start,
    )
    renewed = repository.heartbeat(lease["lease_id"], lease["lease_token"], now=start + timedelta(seconds=60))
    assert renewed["revision"] == 1
    with pytest.raises(WorkbenchPersistenceError) as expired:
        repository.heartbeat(lease["lease_id"], lease["lease_token"], now=start + timedelta(seconds=181))
    assert expired.value.code == "LEASE_EXPIRED"
    expired_record = repository.get(lease["lease_id"])
    assert expired_record["status"] == "expired"
    with pytest.raises(WorkbenchPersistenceError) as delayed_release:
        repository.release(lease["lease_id"], lease["lease_token"], expired_record["revision"])
    assert delayed_release.value.code == "LEASE_NOT_ACTIVE"


def test_running_tasks_become_interrupted_after_restart(database: WorkbenchDatabase) -> None:
    create_shell(database)
    with pytest.raises(ForbiddenPayloadError):
        TaskRecordRepository(database).create({
            "task_id": "SYNTHETIC-TASK-PATH", "case_id": CASE_ID, "kind": "parse",
            "process_binding": {"process_tree_id": "C:\\SYNTHETIC\\process"},
        })
    with pytest.raises(ForbiddenPayloadError):
        TaskRecordRepository(database).create({
            "task_id": "SYNTHETIC-TASK-ERROR-PATH", "case_id": CASE_ID, "kind": "parse",
            "error_summary": "parse failed at C:\\SYNTHETIC\\case.raw",
        })
    terminal = TaskRecordRepository(database).create({
        "task_id": "SYNTHETIC-TASK-TERMINAL", "case_id": CASE_ID, "kind": "parse", "status": "succeeded",
    })
    with pytest.raises(WorkbenchPersistenceError) as transition_error:
        TaskRecordRepository(database).update(terminal["task_id"], {"status": "running"}, terminal["revision"])
    assert transition_error.value.code == "INVALID_TASK_TRANSITION"
    create_parse_task(database, "running")
    interrupted = TaskRecordRepository(database).mark_running_tasks_interrupted()
    assert interrupted[0]["status"] == "interrupted"
    assert interrupted[0]["error_code"] == "TASK_RESTART_INTERRUPTED"


def test_queued_and_cancelling_parse_tasks_become_retryable_after_restart(database: WorkbenchDatabase) -> None:
    create_shell(database)
    workflow = CaseWorkflowRepository(database)
    create_parse_task(database)
    workflow.recover_after_restart()
    assert TaskRecordRepository(database).get(TASK_ID)["status"] == "failed_retryable"
    assert CaseShellRepository(database).get(CASE_ID)["lifecycle"] == "parse_failed_retryable"
    workflow.retry_parse(CASE_ID, TASK_ID)
    workflow.start_parse(CASE_ID, TASK_ID)
    running = TaskRecordRepository(database).get(TASK_ID)
    workflow.cancel_parse(CASE_ID, TASK_ID, running["revision"])
    workflow.recover_after_restart()
    assert TaskRecordRepository(database).get(TASK_ID)["status"] == "interrupted"
    assert CaseShellRepository(database).get(CASE_ID)["lifecycle"] == "parse_failed_retryable"


def test_corrupt_or_incompatible_database_fails_safe(tmp_path: Path) -> None:
    corrupt = database_path_for_deployment(tmp_path, "SYNTHETIC-CORRUPT")
    corrupt.parent.mkdir(parents=True)
    corrupt.write_bytes(b"SYNTHETIC-NOT-SQLITE")
    with pytest.raises(WorkbenchPersistenceError) as error:
        WorkbenchDatabase(corrupt, "SYNTHETIC-CORRUPT")
    assert error.value.code == "SQLITE_CORRUPTED"
    incompatible = database_path_for_deployment(tmp_path, "SYNTHETIC-INCOMPATIBLE")
    db = WorkbenchDatabase(incompatible, "SYNTHETIC-INCOMPATIBLE")
    with db.connect() as connection:
        connection.execute("PRAGMA user_version = 99")
    with pytest.raises(SchemaIncompatibleError):
        WorkbenchDatabase(incompatible, "SYNTHETIC-INCOMPATIBLE")
    incomplete = database_path_for_deployment(tmp_path, "SYNTHETIC-INCOMPLETE")
    incomplete.parent.mkdir(parents=True)
    with sqlite3.connect(incomplete) as connection:
        connection.execute("CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
        connection.execute("INSERT INTO schema_migrations(version, applied_at) VALUES (1, 'SYNTHETIC-TIME')")
        connection.execute("PRAGMA user_version = 1")
    with pytest.raises(SchemaIncompatibleError):
        WorkbenchDatabase(incomplete, "SYNTHETIC-INCOMPLETE")
