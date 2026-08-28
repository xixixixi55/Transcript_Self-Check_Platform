"""使用合成来源与旧版 DTO 的 Phase 1B 服务测试。"""

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
from app.services.case_draft_service import CaseDraftService, _initialize_draft  # noqa: E402
from app.services.case_lifecycle_service import CaseLifecycleService  # noqa: E402
from app.services.document_builder_service import build_record_document  # noqa: E402
from app.services.edit_lease_service import EditLeaseService  # noqa: E402
from app.services.inspection_environment_service import InspectionEnvironmentService  # noqa: E402
from app.services.source_record_service import SourceRecordService  # noqa: E402
from app.services.task_record_service import TaskRecordService  # noqa: E402
from app.repository.shared_defaults_repository import SharedDefaultsRepository  # noqa: E402

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


class SyntheticPassthroughEnvironment:
    def apply_to_report(self, report):
        return copy.deepcopy(report)


class SyntheticEnvironmentRepository:
    def read(self):
        return {
            "operating_system": {
                "product_name": "Windows 10 Pro", "edition_id": "Professional",
                "display_version": "TEST-24H2", "build_number": "22631",
                "architecture": "AMD64",
            },
            "huorong": {"detected": True, "version": "TEST-6.0.7.0"},
        }


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


def make_services(
    database: WorkbenchDatabase, parser, source_service: SourceRecordService,
    environment_service=None,
):
    cases = CaseDraftService(
        database,
        parser=parser,
        source_service=source_service,
        environment_service=environment_service or SyntheticPassthroughEnvironment(),
    )
    return cases, CaseLifecycleService(database)


def source_descriptor(source_service: SourceRecordService, tmp_path: Path, name: str = "SYNTHETIC-REPORT") -> tuple[dict, Path]:
    report_dir = make_report_directory(tmp_path, name)
    return source_service.register_report_directory(str(report_dir)), report_dir


def test_submit_persists_shell_and_task_before_parse(database, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.case_draft_service.utc_now",
        lambda: "2026-08-22T16:30:00+00:00",
    )
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
    assert ready["draft"]["report"]["title"] == REPORT["title"]
    assert ready["draft"]["report"]["introduction"]["entrust_time"] == ""
    assert calls and Path(calls[0][0]) == report_dir


def test_new_draft_leaves_entrust_time_empty_instead_of_using_report_seed():
    parsed_report = copy.deepcopy(REPORT)
    parsed_report["introduction"]["entrust_time"] = "2020年1月2日"

    initialized, field_states = _initialize_draft(
        parsed_report, {}, initialized_at="2026-08-22T16:30:00Z",
    )

    assert initialized["introduction"]["entrust_time"] == ""
    assert field_states["introduction.entrust_time"]["source"] == "system_default"
    assert field_states["introduction.entrust_time"]["confirmation"] == "pending"
    assert parsed_report["introduction"]["entrust_time"] == "2020年1月2日"


def test_parse_applies_deployment_default_template_to_new_draft(database, tmp_path):
    default_ref = {"template_id": "template-SYNTHETIC-default", "version": "1.0.0"}
    defaults = SharedDefaultsRepository(database)
    defaults.patch({"default_template_ref": default_ref}, defaults.get()["revision"])
    source_service = make_source_service(database, tmp_path)
    cases, lifecycle = make_services(
        database, lambda path, output: {"report": copy.deepcopy(REPORT)}, source_service,
    )

    identifiers = cases.submit(source_descriptor(source_service, tmp_path)[0])
    cases.run_parse_task(**identifiers)

    assert lifecycle.detail(identifiers["case_id"])["draft"]["template_ref"] == default_ref


def test_parse_projects_step_three_from_final_hardware_and_local_environment(database, tmp_path):
    defaults = SharedDefaultsRepository(database)
    defaults.patch(
        {"hardware_device": "SYNTHETIC-SELECTED 手机取证工作站"},
        defaults.get()["revision"],
    )
    parsed_report = copy.deepcopy(REPORT)
    parsed_report["inspection"]["process_steps"] = [
        {"step_number": 2, "content": "SYNTHETIC step 2"},
        {"step_number": 3, "content": "SYNTHETIC parser placeholder"},
        {"step_number": 4, "content": "SYNTHETIC step 4"},
    ]
    source_service = make_source_service(database, tmp_path)
    cases, lifecycle = make_services(
        database,
        lambda path, output: {"report": copy.deepcopy(parsed_report)},
        source_service,
        InspectionEnvironmentService(SyntheticEnvironmentRepository()),
    )

    identifiers = cases.submit(source_descriptor(source_service, tmp_path)[0])
    cases.run_parse_task(**identifiers)

    inspection = lifecycle.detail(identifiers["case_id"])["draft"]["report"]["inspection"]
    step_three = next(
        step["content"] for step in inspection["process_steps"]
        if step["step_number"] == 3
    )
    assert inspection["hardware_device"] == "SYNTHETIC-SELECTED 手机取证工作站"
    assert inspection["environment_snapshot"]["operating_system"]["display_name"] == (
        "Windows 11 64位专业版"
    )
    assert "SYNTHETIC-SELECTED 手机取证工作站" in step_three
    assert "火绒安全软件（版本号为TEST-6.0.7.0）" in step_three
    assert inspection["process_steps"][0]["content"] == "SYNTHETIC step 2"
    assert inspection["process_steps"][2]["content"] == "SYNTHETIC step 4"
    word_text = "\n".join(
        command.get("props", {}).get("text", "")
        for command in build_record_document(
            lifecycle.detail(identifiers["case_id"])["draft"]["report"],
        )
        if command.get("type") == "paragraph"
    )
    assert step_three in word_text


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


def test_parse_task_prefixes_new_draft_software_once_without_rewriting_saved_case(
    database, tmp_path, monkeypatch,
):
    parsed_report = copy.deepcopy(REPORT)
    parsed_report["inspection"].update({
        "hardware_device": "SYNTHETIC DEVICE",
        "primary_software": {
            "name": "SYNTHETIC手机大师NEXT", "version": "V1.2.3",
            "display_name": "SYNTHETIC手机大师NEXT V1.2.3",
            "confirmation_status": "confirmed_by_report",
            "provenance": [{"source_type": "report", "adapter": "SYNTHETIC/TEST"}],
            "candidates": [{"name": "SYNTHETIC手机大师NEXT", "version": "V1.2.3"}],
        },
        "software_tools": [
            {"name": "SYNTHETIC手机大师NEXT", "version": "V1.2.3"},
            {"name": "HashMyFiles", "version": "2.51"},
        ],
        "process_steps": [{
            "step_number": 4,
            "content": "启动SYNTHETIC手机大师NEXT软件（版本号为V1.2.3）使用SYNTHETIC手机大师NEXT软件对检材SYNTHETIC-1进行检查。",
        }],
    })
    parsed_report["inspection"]["result"].update({
        "software_name": "SYNTHETIC手机大师NEXT", "software_version": "V1.2.3",
    })
    monkeypatch.setattr(
        "app.services.case_draft_service.company_for_device_name",
        lambda device_name: "TEST美亚柏科" if device_name == "SYNTHETIC DEVICE" else "",
    )
    source_service = make_source_service(database, tmp_path)
    cases, lifecycle = make_services(
        database, lambda path, output: {"report": copy.deepcopy(parsed_report)}, source_service,
    )
    identifiers = cases.submit(source_descriptor(source_service, tmp_path)[0])
    cases.run_parse_task(**identifiers)

    report = lifecycle.detail(identifiers["case_id"])["draft"]["report"]
    assert report["inspection"]["primary_software"]["name"] == "TEST美亚柏科SYNTHETIC手机大师NEXT"
    assert report["inspection"]["software_tools"][0]["name"] == "TEST美亚柏科SYNTHETIC手机大师NEXT"
    assert report["inspection"]["software_tools"][1]["name"] == "HashMyFiles"
    assert report["inspection"]["result"]["software_name"] == "TEST美亚柏科SYNTHETIC手机大师NEXT"
    expected_step = (
        "启动TEST美亚柏科SYNTHETIC手机大师NEXT软件（版本号为V1.2.3）"
        "使用TEST美亚柏科SYNTHETIC手机大师NEXT软件对检材SYNTHETIC-1进行检查。"
    )
    assert report["inspection"]["process_steps"][0]["content"] == expected_step

    word_text = "\n".join(
        command.get("props", {}).get("text", "")
        for command in build_record_document(report)
        if command.get("type") == "paragraph"
    )
    assert expected_step in word_text
    assert "TEST美亚柏科HashMyFiles" not in word_text

    monkeypatch.setattr(
        "app.services.case_draft_service.company_for_device_name", lambda _device_name: "TEST另一公司",
    )
    persisted = lifecycle.detail(identifiers["case_id"])["draft"]["report"]
    assert persisted == report


def test_parse_task_backfills_case_shell_from_parser_metadata_without_overwriting_user_values(database, tmp_path):
    parsed_report = copy.deepcopy(REPORT)
    parsed_report["introduction"]["case_summary"] = "SYNTHETIC-REPORT-SUMMARY"
    parser_result = {
        "report": parsed_report,
        "_case_metadata": {
            "case_name": "SYNTHETIC-REPORT-NAME",
            "case_number": "SYNTHETIC-REPORT-NUMBER",
            "case_summary": "SYNTHETIC-REPORT-SUMMARY",
        },
    }
    source_service = make_source_service(database, tmp_path)
    cases, lifecycle = make_services(
        database, lambda path, output: copy.deepcopy(parser_result), source_service,
    )
    identifiers = cases.submit(
        source_descriptor(source_service, tmp_path)[0],
        case_name="SYNTHETIC-MANUAL-NAME",
        case_summary="SYNTHETIC-MANUAL-SUMMARY",
        case_number="SYNTHETIC-MANUAL-NUMBER",
    )
    cases.run_parse_task(**identifiers)

    detail = lifecycle.detail(identifiers["case_id"])
    assert detail["shell"]["case_name"] == "SYNTHETIC-MANUAL-NAME"
    assert detail["shell"]["case_summary"] == "SYNTHETIC-MANUAL-SUMMARY"
    assert detail["shell"]["case_number"] == "SYNTHETIC-MANUAL-NUMBER"

    blank_identifiers = cases.submit(source_descriptor(source_service, tmp_path, "SYNTHETIC-REPORT-2")[0])
    cases.run_parse_task(**blank_identifiers)
    blank_detail = lifecycle.detail(blank_identifiers["case_id"])
    assert blank_detail["shell"]["case_name"] == "SYNTHETIC-REPORT-NAME"
    assert blank_detail["shell"]["case_summary"] == "SYNTHETIC-REPORT-SUMMARY"
    assert blank_detail["shell"]["case_number"] == "SYNTHETIC-REPORT-NUMBER"
    assert blank_detail["draft"]["case_name"] == "SYNTHETIC-REPORT-NAME"
    assert blank_detail["draft"]["case_summary"] == "SYNTHETIC-REPORT-SUMMARY"


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
    completeness_path = "introduction.evidence_list.completeness"
    submitted_states[completeness_path] = {
        "field_path": completeness_path, "source": "user", "confirmation": "confirmed",
        "revision": 1, "last_changed_at": "2026-08-21T00:00:00Z",
    }

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
    assert persisted["field_states"][completeness_path]["confirmation"] == "confirmed"
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


def test_lease_takeover_is_audited_and_delete_preflight_allows_explicit_delete(database, tmp_path):
    source_service = make_source_service(database, tmp_path)
    cases, lifecycle = make_services(database, lambda path, output: {"report": copy.deepcopy(REPORT)}, source_service)
    identifiers = cases.submit(source_descriptor(source_service, tmp_path)[0])
    lease_service = EditLeaseService(database)
    first = lease_service.acquire(identifiers["case_id"], IDENTITY)
    with pytest.raises(WorkbenchPersistenceError) as conflict:
        lease_service.acquire(identifiers["case_id"], {**IDENTITY, "session_id": "SYNTHETIC-SESSION-2"})
    assert conflict.value.code == "LEASE_CONFLICT"
    preflight = lifecycle.delete_preflight(identifiers["case_id"])
    assert preflight == {"allowed": True, "blockers": []}
    assert first["lease_token"] not in str(preflight)


def test_delete_case_removes_workbench_records_after_confirmation_path(database, tmp_path):
    source_service = make_source_service(database, tmp_path)
    cases, lifecycle = make_services(
        database, lambda path, output: {"report": copy.deepcopy(REPORT)}, source_service,
    )
    identifiers = cases.submit(source_descriptor(source_service, tmp_path)[0])
    cases.run_parse_task(**identifiers)

    deleted = lifecycle.delete_case(identifiers["case_id"])

    assert deleted == {"case_id": identifiers["case_id"], "deleted": True}
    with database.connect() as connection:
        for table in ("case_shells", "case_drafts", "source_records", "task_records"):
            assert connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE case_id=?", (identifiers["case_id"],)
            ).fetchone()[0] == 0
    assert lifecycle.list(0, 6)["items"] == []
    with pytest.raises(WorkbenchPersistenceError, match="CASE_NOT_FOUND"):
        lifecycle.detail(identifiers["case_id"])


def test_delete_case_allows_queued_case_after_explicit_confirmation(database, tmp_path):
    source_service = make_source_service(database, tmp_path)
    cases, lifecycle = make_services(
        database, lambda path, output: {"report": copy.deepcopy(REPORT)}, source_service,
    )
    identifiers = cases.submit(source_descriptor(source_service, tmp_path)[0])

    assert lifecycle.delete_case(identifiers["case_id"]) == {
        "case_id": identifiers["case_id"], "deleted": True,
    }
    with database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM case_shells WHERE case_id=?", (identifiers["case_id"],)
        ).fetchone()[0] == 0


def test_delete_case_allows_formal_lifecycle_after_explicit_confirmation(database, tmp_path):
    source_service = make_source_service(database, tmp_path)
    cases, lifecycle = make_services(
        database, lambda path, output: {"report": copy.deepcopy(REPORT)}, source_service,
    )
    identifiers = cases.submit(source_descriptor(source_service, tmp_path)[0])
    cases.run_parse_task(**identifiers)
    with database.transaction() as connection:
        connection.execute(
            "UPDATE case_shells SET lifecycle='exported' WHERE case_id=?",
            (identifiers["case_id"],),
        )

    assert lifecycle.delete_case(identifiers["case_id"]) == {
        "case_id": identifiers["case_id"], "deleted": True,
    }


@pytest.mark.parametrize("lifecycle_state", [
    "parse_failed_retryable", "archive_interrupted", "exported",
])
def test_delete_case_allows_reported_manual_acceptance_states(
    database, tmp_path, lifecycle_state,
):
    source_service = make_source_service(database, tmp_path)
    cases, lifecycle = make_services(
        database, lambda path, output: {"report": copy.deepcopy(REPORT)}, source_service,
    )
    identifiers = cases.submit(source_descriptor(source_service, tmp_path)[0])
    with database.transaction() as connection:
        connection.execute(
            "UPDATE case_shells SET lifecycle=? WHERE case_id=?",
            (lifecycle_state, identifiers["case_id"]),
        )
        if lifecycle_state == "parse_failed_retryable":
            connection.execute(
                "UPDATE task_records SET status='failed_retryable' WHERE task_id=?",
                (identifiers["task_id"],),
            )

    assert lifecycle.delete_case(identifiers["case_id"]) == {
        "case_id": identifiers["case_id"], "deleted": True,
    }


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

    unrestricted = tmp_path / "SYNTHETIC-OUTSIDE" / "SYNTHETIC-REPORT"
    shutil.copytree(make_report_directory(tmp_path, "SYNTHETIC-BASELINE"), unrestricted)
    descriptor = source_service.register_report_directory(
        str(unrestricted), source_authorization_enabled=False,
    )
    assert descriptor["source_type"] == "report_directory"

    invalid_external = tmp_path / "SYNTHETIC-OUTSIDE" / "SYNTHETIC-INVALID"
    invalid_external.mkdir(parents=True)
    with pytest.raises(WorkbenchPersistenceError) as structure_error:
        source_service.register_report_directory(
            str(invalid_external), source_authorization_enabled=False,
        )
    assert structure_error.value.code == "SOURCE_STRUCTURE_INVALID"

    with pytest.raises(ArchiveAuthorizationError) as enabled_error:
        source_service.register_report_directory(str(unrestricted), source_authorization_enabled=True)
    assert enabled_error.value.code == "ARCHIVE_INPUT_ROOT_NOT_ALLOWED"

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
