"""Phase 1B service tests using synthetic sources and Legacy DTOs."""

from __future__ import annotations

import copy
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import WorkbenchDatabase, database_path_for_deployment  # noqa: E402
from app.repository.archive_authorization_repository import ArchiveAuthorizationError  # noqa: E402
from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402
from app.services.archive_authorization_service import ArchiveAuthorizationService  # noqa: E402
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


def make_report_directory(tmp_path: Path, name: str = "SYNTHETIC-REPORT") -> Path:
    report_dir = tmp_path / "SYNTHETIC-ALLOWED-ROOT" / name
    data_dir = report_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "data_case_info.json").write_text(
        json.dumps({"contents": []}), encoding="utf-8",
    )
    (data_dir / "data_device_lists.json").write_text(
        json.dumps({"contents": [{"c3": "SYNTHETIC-2026-01-01"}]}), encoding="utf-8",
    )
    (data_dir / "data_report_info.json").write_text(
        json.dumps({"contents": []}), encoding="utf-8",
    )
    return report_dir


def make_source_service(database: WorkbenchDatabase, tmp_path: Path) -> SourceRecordService:
    allowed_root = tmp_path / "SYNTHETIC-ALLOWED-ROOT"
    output_root = tmp_path / "SYNTHETIC-OUTPUT-ROOT"
    allowed_root.mkdir(exist_ok=True)
    output_root.mkdir(exist_ok=True)
    return SourceRecordService(
        database,
        ArchiveAuthorizationService(str(allowed_root), str(output_root)),
    )


def make_services(database: WorkbenchDatabase, parser, source_service: SourceRecordService):
    cases = CaseDraftService(database, parser=parser, source_service=source_service)
    return cases, CaseLifecycleService(database)


def source_descriptor(source_service: SourceRecordService, tmp_path: Path, name: str = "SYNTHETIC-REPORT") -> tuple[dict, Path]:
    report_dir = make_report_directory(tmp_path, name)
    return source_service.register_report_directory(str(report_dir)), report_dir


def test_submit_persists_shell_and_task_before_parse(database, tmp_path):
    calls = []

    def parser(path, output):
        calls.append((path, output))
        return {"report": copy.deepcopy(REPORT)}

    source_service = make_source_service(database, tmp_path)
    cases, lifecycle = make_services(database, parser, source_service)
    descriptor, report_dir = source_descriptor(source_service, tmp_path)
    identifiers = cases.submit(descriptor, case_name="SYNTHETIC-CASE")
    queued = lifecycle.detail(identifiers["case_id"])
    assert queued["shell"]["lifecycle"] == "parse_queued"
    assert queued["parse_task"]["status"] == "queued"
    assert queued["draft"] is None
    cases.run_parse_task(identifiers["case_id"], identifiers["task_id"])
    ready = lifecycle.detail(identifiers["case_id"])
    assert ready["shell"]["lifecycle"] == "review_ready"
    assert ready["parse_task"]["status"] == "succeeded"
    assert ready["draft"]["report"] == REPORT
    assert calls and Path(calls[0][0]) == report_dir


def test_parse_task_enriches_report_device_type_for_review_editor(database, tmp_path):
    parsed_report = copy.deepcopy(REPORT)
    parsed_report["introduction"]["evidence_list"] = [{
        "id": "SYNTHETIC-EVIDENCE-1", "evidence_number": "SYNTHETIC-1",
        "device_type": "手机", "device_name": "SYNTHETIC-BRAND SYNTHETIC-MODEL",
        "brand": "SYNTHETIC-BRAND", "model": "SYNTHETIC-MODEL",
        "imei1": "123456789012345", "imei2": "",
    }]
    source_service = make_source_service(database, tmp_path)
    cases, lifecycle = make_services(
        database, lambda path, output: {"report": copy.deepcopy(parsed_report)}, source_service,
    )
    identifiers = cases.submit(source_descriptor(source_service, tmp_path)[0])
    cases.run_parse_task(**identifiers)

    evidence = lifecycle.detail(identifiers["case_id"])["draft"]["report"]["introduction"]["evidence_list"][0]
    assert evidence["device_name"] == "SYNTHETIC-BRAND SYNTHETIC-MODEL"
    assert evidence["imei1"] == "123456789012345"
    assert evidence["material_type"] == "phone"
    assert evidence["material_type_status"] == "confirmed_by_report"


def test_case_save_persists_dragged_card_order_and_field_provenance(database, tmp_path):
    parsed_report = copy.deepcopy(REPORT)
    parsed_report["introduction"].update({
        "evidence_list": [
            {"id": "SYNTHETIC-EVIDENCE-10", "device_type": "SYNTHETIC", "evidence_number": "SYNTHETIC-10", "model": "SYNTHETIC-10"},
            {"id": "SYNTHETIC-EVIDENCE-2", "device_type": "SYNTHETIC", "evidence_number": "SYNTHETIC-2", "model": "SYNTHETIC-2"},
        ],
        "inspectors": [
            {"name": "SYNTHETIC-A", "unit": "SYNTHETIC-U", "badge_number": "SYNTHETIC-001"},
            {"name": "SYNTHETIC-B", "unit": "SYNTHETIC-U", "badge_number": "SYNTHETIC-002"},
        ],
    })
    parsed_report["attachments"]["photo_groups"] = [{
        "material_id": "SYNTHETIC-MATERIAL-1", "material_number": "SYNTHETIC-1",
        "display_text": "SYNTHETIC", "ordered_image_ids": ["SYNTHETIC-IMG-1", "SYNTHETIC-IMG-2"], "source_order": 0,
    }]
    source_service = make_source_service(database, tmp_path)
    cases, lifecycle = make_services(
        database, lambda path, output: {"report": copy.deepcopy(parsed_report)}, source_service,
    )
    identifiers = cases.submit(source_descriptor(source_service, tmp_path)[0])
    cases.run_parse_task(**identifiers)
    detail = lifecycle.detail(identifiers["case_id"])
    assert detail["parse_task"]["status"] == "succeeded", detail["parse_task"]["error_code"]
    draft = detail["draft"]
    report = copy.deepcopy(draft["report"])
    report["introduction"]["evidence_list"].reverse()
    report["introduction"]["evidence_list"][0]["model"] = "SYNTHETIC-USER-MODEL"
    report["introduction"]["inspector_snapshots"].reverse()
    submitted_states = copy.deepcopy(draft["field_states"])
    model_path = f"evidence.{report['introduction']['evidence_list'][0]['evidence_id']}.model"
    submitted_states[model_path]["confirmation"] = "pending"

    saved = lifecycle.save_draft({
        "case_id": identifiers["case_id"], "report": report, "field_states": submitted_states,
        "asset_refs": [], "lifecycle": "review_ready",
    }, draft["revision"], None, None)
    persisted = saved["draft"]

    assert saved["draft_save_status"] == {"status": "saved", "revision": persisted["revision"]}
    assert [item["evidence_number"] for item in persisted["report"]["introduction"]["evidence_list"]] == [
        "SYNTHETIC-10", "SYNTHETIC-2",
    ]
    assert [item["selected_order"] for item in persisted["report"]["introduction"]["inspector_snapshots"]] == [0, 1]
    assert [item["name"] for item in persisted["report"]["introduction"]["inspector_snapshots"]] == [
        "SYNTHETIC-B", "SYNTHETIC-A",
    ]
    assert persisted["field_states"][model_path]["source"] == "user"
    assert persisted["field_states"][model_path]["confirmation"] == "pending"
    assert persisted["field_states"]["inspectors." + persisted["report"]["introduction"]["inspector_snapshots"][0]["snapshot_id"] + ".name"]["source"] == "report"
    assert persisted["field_states"]["photo_groups.SYNTHETIC-MATERIAL-1"]["source"] == "report"


def test_case_detail_retries_a_mixed_parse_completion_snapshot(database, tmp_path, monkeypatch):
    source_service = make_source_service(database, tmp_path)
    cases, lifecycle = make_services(database, lambda path, output: {"report": copy.deepcopy(REPORT)}, source_service)
    identifiers = cases.submit(source_descriptor(source_service, tmp_path)[0])
    cases.run_parse_task(**identifiers)
    original_get = lifecycle.shells.get
    calls = {"count": 0}

    def mixed_shell(case_id):
        calls["count"] += 1
        value = original_get(case_id)
        if calls["count"] == 1:
            return {**value, "lifecycle": "parsing", "report_available": False, "revision": value["revision"] - 1}
        return value

    monkeypatch.setattr(lifecycle.shells, "get", mixed_shell)
    detail = lifecycle.detail(identifiers["case_id"])

    assert calls["count"] >= 3
    assert detail["shell"]["lifecycle"] == "review_ready"
    assert detail["parse_task"]["status"] == "succeeded"
    assert detail["draft"] is not None


def test_parse_failure_retains_retryable_case_and_retry(database, tmp_path):
    attempts = {"count": 0}

    def parser(path, output):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise ValueError("SYNTHETIC private path failure")
        return {"report": copy.deepcopy(REPORT)}

    source_service = make_source_service(database, tmp_path)
    cases, lifecycle = make_services(database, parser, source_service)
    descriptor, _ = source_descriptor(source_service, tmp_path)
    identifiers = cases.submit(descriptor)
    cases.run_parse_task(**identifiers)
    failed = lifecycle.detail(identifiers["case_id"])
    assert failed["shell"]["lifecycle"] == "parse_failed_retryable"
    assert failed["parse_task"]["status"] == "failed_retryable"
    assert failed["draft"] is None
    cases.retry(identifiers["case_id"])
    cases.run_parse_task(**identifiers)
    assert lifecycle.detail(identifiers["case_id"])["shell"]["lifecycle"] == "review_ready"


def test_invalid_source_requires_reselection_without_exposing_locator(database, tmp_path):
    source_service = make_source_service(database, tmp_path)
    descriptor, report_dir = source_descriptor(source_service, tmp_path)
    cases, lifecycle = make_services(database, lambda path, output: {"report": copy.deepcopy(REPORT)}, source_service)
    identifiers = cases.submit(descriptor)
    shutil.rmtree(report_dir)
    cases.run_parse_task(**identifiers)
    detail = lifecycle.detail(identifiers["case_id"])
    assert detail["source"]["access_status"] == "requires_reselection"
    assert detail["parse_task"]["error_code"] == "SOURCE_RESELECTION_REQUIRED"
    assert "internal_path" not in str(detail)


def test_source_replacement_requires_case_revision_and_rebinds_opaque_source(database, tmp_path):
    source_service = make_source_service(database, tmp_path)
    descriptor, _ = source_descriptor(source_service, tmp_path)
    cases, lifecycle = make_services(database, lambda path, output: {"report": copy.deepcopy(REPORT)}, source_service)
    identifiers = cases.submit(descriptor)
    cases.run_parse_task(**identifiers)
    current = lifecycle.detail(identifiers["case_id"])
    replacement_dir = make_report_directory(tmp_path, "SYNTHETIC-REPLACEMENT")
    with pytest.raises(WorkbenchPersistenceError) as conflict:
        source_service.replace_case_source(
            identifiers["case_id"], str(replacement_dir), current["shell"]["revision"] - 1
        )
    assert conflict.value.code == "REVISION_CONFLICT"
    updated = source_service.replace_case_source(
        identifiers["case_id"], str(replacement_dir), current["shell"]["revision"]
    )
    assert updated["source_id"] != identifiers["source_id"]
    assert updated["access_status"] == "pending"
    reset = lifecycle.detail(identifiers["case_id"])
    assert reset["shell"]["source_id"] == updated["source_id"]
    assert reset["shell"]["lifecycle"] == "parse_queued"
    assert reset["parse_task"]["status"] == "queued"
    assert reset["draft"] is None
    cases.run_parse_task(identifiers["case_id"], identifiers["task_id"])
    assert lifecycle.detail(identifiers["case_id"])["shell"]["lifecycle"] == "review_ready"


def test_revision_conflict_and_dual_save_partial_failure_are_visible(database, tmp_path):
    source_service = make_source_service(database, tmp_path)
    cases, lifecycle = make_services(database, lambda path, output: {"report": copy.deepcopy(REPORT)}, source_service)
    identifiers = cases.submit(source_descriptor(source_service, tmp_path)[0])
    cases.run_parse_task(**identifiers)
    draft = lifecycle.detail(identifiers["case_id"])["draft"]
    saved = lifecycle.save_draft({"case_id": identifiers["case_id"], "report": REPORT, "field_states": draft["field_states"], "asset_refs": [], "lifecycle": "review_ready"}, 1, {"document_number": "C:\\SYNTHETIC\\forbidden"}, 0, IDENTITY)
    assert saved["draft_save_status"]["status"] == "saved"
    assert saved["shared_defaults_save_status"]["status"] == "failed"
    conflict = lifecycle.save_draft({"case_id": identifiers["case_id"], "report": {**REPORT, "title": "SYNTHETIC-NEW"}, "field_states": draft["field_states"], "asset_refs": [], "lifecycle": "review_ready"}, 1, None, None)
    assert conflict["draft_save_status"]["status"] == "conflict"
    assert lifecycle.detail(identifiers["case_id"])["draft"]["report"]["title"] == REPORT["title"]


def test_restart_recovery_is_interrupted_and_not_success(database, tmp_path):
    source_service = make_source_service(database, tmp_path)
    cases, lifecycle = make_services(database, lambda path, output: {"report": copy.deepcopy(REPORT)}, source_service)
    identifiers = cases.submit(source_descriptor(source_service, tmp_path)[0])
    cases.workflow.start_parse(identifiers["case_id"], identifiers["task_id"])
    interrupted = TaskRecordService(database).recover_after_restart()
    detail = lifecycle.detail(identifiers["case_id"])
    assert interrupted == [identifiers["task_id"]]
    assert detail["parse_task"]["status"] == "interrupted"
    assert detail["shell"]["lifecycle"] == "parse_failed_retryable"


def test_lease_takeover_is_audited_and_delete_preflight_blocks_active_work(database, tmp_path):
    source_service = make_source_service(database, tmp_path)
    cases, lifecycle = make_services(database, lambda path, output: {"report": copy.deepcopy(REPORT)}, source_service)
    identifiers = cases.submit(source_descriptor(source_service, tmp_path)[0])
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


def test_directory_source_rejects_archives_outside_roots_and_invalid_structure(database, tmp_path):
    source_service = make_source_service(database, tmp_path)
    archive_path = tmp_path / "SYNTHETIC-REPORT.zip"
    archive_path.write_bytes(b"SYNTHETIC/TEST/ARCHIVE")
    with pytest.raises(WorkbenchPersistenceError) as archive_error:
        source_service.register_report_directory(str(archive_path))
    assert archive_error.value.code == "SOURCE_ARCHIVE_NOT_ALLOWED"

    outside = tmp_path / "SYNTHETIC-OUTSIDE" / "report"
    outside.mkdir(parents=True)
    with pytest.raises(ArchiveAuthorizationError) as root_error:
        source_service.register_report_directory(str(outside))
    assert root_error.value.code == "ARCHIVE_INPUT_ROOT_NOT_ALLOWED"

    invalid = tmp_path / "SYNTHETIC-ALLOWED-ROOT" / "SYNTHETIC-INVALID"
    invalid.mkdir(parents=True)
    with pytest.raises(WorkbenchPersistenceError) as structure_error:
        source_service.register_report_directory(str(invalid))
    assert structure_error.value.code == "SOURCE_STRUCTURE_INVALID"


def test_archive_decision_persists_deferred_then_allows_explicit_legacy_start(database, tmp_path):
    source_service = make_source_service(database, tmp_path)
    cases, lifecycle = make_services(database, lambda path, output: {"report": copy.deepcopy(REPORT)}, source_service)
    identifiers = cases.submit(source_descriptor(source_service, tmp_path)[0])
    cases.run_parse_task(**identifiers)
    ready = lifecycle.detail(identifiers["case_id"])

    deferred = lifecycle.decide_archive(
        identifiers["case_id"], "deferred", ready["shell"]["revision"], IDENTITY,
    )
    assert deferred["shell"]["lifecycle"] == "archive_deferred"
    assert deferred["draft"]["lifecycle"] == "archive_deferred"

    with pytest.raises(WorkbenchPersistenceError) as immediate:
        lifecycle.decide_archive(
            identifiers["case_id"], "immediate", deferred["shell"]["revision"], IDENTITY,
        )
    assert immediate.value.code == "ARCHIVE_ATTEMPT_REQUIRED"


def test_source_locator_is_not_written_to_public_sqlite_fields(database, tmp_path):
    source_service = make_source_service(database, tmp_path)
    descriptor, report_dir = source_descriptor(source_service, tmp_path)
    cases = CaseDraftService(database, source_service=source_service)
    cases.submit(descriptor)
    connection = database.connect()
    try:
        raw = connection.execute(
            "SELECT internal_path, allowed_root FROM source_records WHERE source_id = ?",
            (descriptor["source_id"],),
        ).fetchone()
    finally:
        connection.close()
    assert raw["internal_path"].startswith("locator://")
    assert raw["allowed_root"].startswith("root://")
    assert str(report_dir) not in json.dumps(dict(raw))
