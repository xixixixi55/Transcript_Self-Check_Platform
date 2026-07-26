"""Phase 1B service tests using synthetic sources and Legacy DTOs."""

from __future__ import annotations

import copy
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import WorkbenchDatabase, database_path_for_deployment  # noqa: E402
from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402
from app.services.case_draft_service import CaseDraftService  # noqa: E402
from app.services.case_lifecycle_service import CaseLifecycleService  # noqa: E402
from app.services.edit_lease_service import EditLeaseService  # noqa: E402
from app.services.source_record_service import SourceRecordService  # noqa: E402
from app.services.task_record_service import TaskRecordService  # noqa: E402

REPORT = {
    "title": "SYNTHETIC/TEST/InspectionReport", "document_number": "SYNTHETIC-DOC-001",
    "introduction": {
        "entrust_unit": "SYNTHETIC-UNIT", "entrust_persons": [], "entrust_time": "",
        "case_summary": "SYNTHETIC", "evidence_list": [], "inspection_requirement": "",
        "inspection_time_range": "", "inspectors": [], "inspection_place": "",
    },
    "inspection": {
        "method": "", "hardware_device": "", "software_tools": [], "process_steps": [],
        "result": {"evidence_number": "", "software_name": "", "software_version": "", "data_summary": "", "rar_filename": "", "md5_hash": "", "file_size": ""},
    },
    "attachments": {"extract_list": {"columns": [], "rows": []}, "photo_ids": [], "disc_number": ""},
}
IDENTITY = {"identity_kind": "local_session", "client_instance_id": "SYNTHETIC-CLIENT", "session_id": "SYNTHETIC-SESSION", "deployment_instance_id": "SYNTHETIC-DEPLOYMENT"}


@pytest.fixture()
def database(tmp_path: Path) -> WorkbenchDatabase:
    return WorkbenchDatabase(database_path_for_deployment(tmp_path, "SYNTHETIC-DEPLOYMENT"), "SYNTHETIC-DEPLOYMENT")


def make_services(database: WorkbenchDatabase, parser):
    cases = CaseDraftService(database, parser=parser)
    return cases, CaseLifecycleService(database)


def source_descriptor(database: WorkbenchDatabase, tmp_path: Path) -> dict:
    return SourceRecordService(database).store_uploaded_archive(b"SYNTHETIC/TEST/archive", ".zip")


def test_submit_persists_shell_and_task_before_parse(database, tmp_path):
    calls = []

    def parser(path, output):
        calls.append((path, output))
        return {"report": copy.deepcopy(REPORT)}

    cases, lifecycle = make_services(database, parser)
    identifiers = cases.submit(source_descriptor(database, tmp_path), case_name="SYNTHETIC-CASE")
    queued = lifecycle.detail(identifiers["case_id"])
    assert queued["shell"]["lifecycle"] == "parse_queued"
    assert queued["parse_task"]["status"] == "queued"
    assert queued["draft"] is None
    cases.run_parse_task(identifiers["case_id"], identifiers["task_id"])
    ready = lifecycle.detail(identifiers["case_id"])
    assert ready["shell"]["lifecycle"] == "review_ready"
    assert ready["parse_task"]["status"] == "succeeded"
    assert ready["draft"]["report"] == REPORT
    assert calls and calls[0][0].suffix == ".zip"


def test_parse_failure_retains_retryable_case_and_retry(database, tmp_path):
    attempts = {"count": 0}

    def parser(path, output):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise ValueError("SYNTHETIC private path failure")
        return {"report": copy.deepcopy(REPORT)}

    cases, lifecycle = make_services(database, parser)
    identifiers = cases.submit(source_descriptor(database, tmp_path))
    cases.run_parse_task(**identifiers)
    failed = lifecycle.detail(identifiers["case_id"])
    assert failed["shell"]["lifecycle"] == "parse_failed_retryable"
    assert failed["parse_task"]["status"] == "failed_retryable"
    assert failed["draft"] is None
    cases.retry(identifiers["case_id"])
    cases.run_parse_task(**identifiers)
    assert lifecycle.detail(identifiers["case_id"])["shell"]["lifecycle"] == "review_ready"


def test_invalid_source_requires_reselection_without_exposing_locator(database, tmp_path):
    descriptor = source_descriptor(database, tmp_path)
    cases, lifecycle = make_services(database, lambda path, output: {"report": copy.deepcopy(REPORT)})
    identifiers = cases.submit(descriptor)
    descriptor["cleanup_path"].unlink()
    cases.run_parse_task(**identifiers)
    detail = lifecycle.detail(identifiers["case_id"])
    assert detail["source"]["access_status"] == "requires_reselection"
    assert detail["parse_task"]["error_code"] == "SOURCE_RESELECTION_REQUIRED"
    assert "internal_path" not in str(detail)


def test_source_replacement_requires_case_revision_and_rebinds_opaque_source(database, tmp_path):
    descriptor = source_descriptor(database, tmp_path)
    cases, lifecycle = make_services(database, lambda path, output: {"report": copy.deepcopy(REPORT)})
    identifiers = cases.submit(descriptor)
    cases.run_parse_task(**identifiers)
    current = lifecycle.detail(identifiers["case_id"])
    replacement = SourceRecordService(database)
    with pytest.raises(WorkbenchPersistenceError) as conflict:
        replacement.replace_case_source(
            identifiers["case_id"], b"SYNTHETIC/TEST/new", ".zip", current["shell"]["revision"] - 1
        )
    assert conflict.value.code == "REVISION_CONFLICT"
    updated = replacement.replace_case_source(
        identifiers["case_id"], b"SYNTHETIC/TEST/new", ".zip", current["shell"]["revision"]
    )
    assert updated["source_id"] != identifiers["source_id"]
    assert updated["access_status"] == "available"
    assert lifecycle.detail(identifiers["case_id"])["shell"]["source_id"] == updated["source_id"]


def test_revision_conflict_and_dual_save_partial_failure_are_visible(database, tmp_path):
    cases, lifecycle = make_services(database, lambda path, output: {"report": copy.deepcopy(REPORT)})
    identifiers = cases.submit(source_descriptor(database, tmp_path))
    cases.run_parse_task(**identifiers)
    draft = lifecycle.detail(identifiers["case_id"])["draft"]
    saved = lifecycle.save_draft({"case_id": identifiers["case_id"], "report": REPORT, "field_states": draft["field_states"], "asset_refs": [], "lifecycle": "review_ready"}, 1, {"document_number": "C:\\SYNTHETIC\\forbidden"}, 0, IDENTITY)
    assert saved["draft_save_status"]["status"] == "saved"
    assert saved["shared_defaults_save_status"]["status"] == "failed"
    conflict = lifecycle.save_draft({"case_id": identifiers["case_id"], "report": {**REPORT, "title": "SYNTHETIC-NEW"}, "field_states": draft["field_states"], "asset_refs": [], "lifecycle": "review_ready"}, 1, None, None)
    assert conflict["draft_save_status"]["status"] == "conflict"
    assert lifecycle.detail(identifiers["case_id"])["draft"]["report"]["title"] == REPORT["title"]


def test_restart_recovery_is_interrupted_and_not_success(database, tmp_path):
    cases, lifecycle = make_services(database, lambda path, output: {"report": copy.deepcopy(REPORT)})
    identifiers = cases.submit(source_descriptor(database, tmp_path))
    cases.workflow.start_parse(identifiers["case_id"], identifiers["task_id"])
    interrupted = TaskRecordService(database).recover_after_restart()
    detail = lifecycle.detail(identifiers["case_id"])
    assert interrupted == [identifiers["task_id"]]
    assert detail["parse_task"]["status"] == "interrupted"
    assert detail["shell"]["lifecycle"] == "parse_failed_retryable"


def test_lease_takeover_is_audited_and_delete_preflight_blocks_active_work(database, tmp_path):
    cases, lifecycle = make_services(database, lambda path, output: {"report": copy.deepcopy(REPORT)})
    identifiers = cases.submit(source_descriptor(database, tmp_path))
    lease_service = EditLeaseService(database)
    first = lease_service.acquire(identifiers["case_id"], IDENTITY)
    with pytest.raises(WorkbenchPersistenceError) as conflict:
        lease_service.acquire(identifiers["case_id"], {**IDENTITY, "session_id": "SYNTHETIC-SESSION-2"})
    assert conflict.value.code == "LEASE_CONFLICT"
    blocked = lifecycle.delete_preflight(identifiers["case_id"])
    assert blocked["allowed"] is False
    assert "ACTIVE_OR_RETRYABLE_TASK" in blocked["blockers"]
    assert "ACTIVE_EDIT_LEASE" in blocked["blockers"]
    assert first["lease_token"] not in str(blocked)
