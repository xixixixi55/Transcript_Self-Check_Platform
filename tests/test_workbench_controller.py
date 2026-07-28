"""HTTP contract tests for directory-source workbench cases."""

from __future__ import annotations

import copy
import json
import os
import shutil
import sys
import time
from threading import Event
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import WorkbenchDatabase, database_path_for_deployment  # noqa: E402
from app.services.archive_authorization_service import ArchiveAuthorizationService  # noqa: E402
from app.services.archive_attempt_service import ArchiveAttemptService  # noqa: E402
from app.services.case_draft_service import CaseDraftService  # noqa: E402
from app.services.case_lifecycle_service import CaseLifecycleService  # noqa: E402
from app.services.edit_lease_service import EditLeaseService  # noqa: E402
from app.services.shared_defaults_service import SharedDefaultsService  # noqa: E402
from app.services.source_record_service import SourceRecordService  # noqa: E402
from app.services.task_record_service import TaskRecordService  # noqa: E402
from app.services.workbench_factory_service import WorkbenchServices  # noqa: E402

REPORT = {
    "title": "SYNTHETIC/TEST/InspectionReport", "document_number": "SYNTHETIC-DOC-001",
    "introduction": {"entrust_unit": "SYNTHETIC", "entrust_persons": [], "entrust_time": "", "case_summary": "SYNTHETIC", "evidence_list": [], "inspection_requirement": "", "inspection_time_range": "", "inspectors": [], "inspection_place": ""},
    "inspection": {"method": "", "hardware_device": "", "software_tools": [], "process_steps": [], "result": {"evidence_number": "", "software_name": "", "software_version": "", "data_summary": "", "rar_filename": "", "md5_hash": "", "file_size": ""}},
    "attachments": {"extract_list": {"columns": [], "rows": []}, "photo_ids": [], "disc_number": ""},
}
IDENTITY = {"identity_kind": "local_session", "client_instance_id": "SYNTHETIC-CLIENT", "session_id": "SYNTHETIC-SESSION", "deployment_instance_id": "SYNTHETIC-DEPLOYMENT"}


@pytest.fixture()
def app_services(tmp_path: Path):
    database = WorkbenchDatabase(database_path_for_deployment(tmp_path, "SYNTHETIC-DEPLOYMENT"), "SYNTHETIC-DEPLOYMENT")
    parser = lambda path, output: {"report": copy.deepcopy(REPORT)}
    allowed_root = tmp_path / "SYNTHETIC-ALLOWED-ROOT"
    output_root = tmp_path / "SYNTHETIC-OUTPUT-ROOT"
    allowed_root.mkdir()
    output_root.mkdir()
    source_service = SourceRecordService(
        database, ArchiveAuthorizationService(str(allowed_root), str(output_root)),
    )
    report_dir = allowed_root / "SYNTHETIC-REPORT"
    data_dir = report_dir / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "data_case_info.json").write_text(json.dumps({"contents": []}), encoding="utf-8")
    (data_dir / "data_device_lists.json").write_text(json.dumps({"contents": [{"c3": "SYNTHETIC-C3"}]}), encoding="utf-8")
    (data_dir / "data_report_info.json").write_text(json.dumps({"contents": []}), encoding="utf-8")
    services = WorkbenchServices(database, CaseDraftService(database, parser=parser, source_service=source_service), CaseLifecycleService(database), SharedDefaultsService(database), EditLeaseService(database), source_service, TaskRecordService(database))
    services.archive_attempts = ArchiveAttemptService(database, output_root)
    services.synthetic_report_dir = report_dir
    return services


def _wait_for_parse(
    client: TestClient, case_id: str, *, timeout_seconds: float = 5.0, poll_interval: float = 0.01,
) -> dict:
    terminal_task_statuses = {"succeeded", "failed_retryable", "failed_terminal", "cancelled", "interrupted", "blocked"}
    active_lifecycles = {"case_created", "parse_queued", "parsing", "cancelling"}
    deadline = time.monotonic() + timeout_seconds
    attempts = 0
    last_detail: dict | None = None
    while True:
        attempts += 1
        last_detail = client.get(f"/api/v1/workbench/cases/{case_id}").json()["data"]
        lifecycle = last_detail["shell"]["lifecycle"]
        task_status = last_detail["parse_task"]["status"]
        if task_status == "succeeded" and lifecycle == "review_ready":
            return last_detail
        if task_status in terminal_task_statuses and lifecycle not in active_lifecycles:
            return last_detail
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            shell = last_detail["shell"]
            task = last_detail["parse_task"]
            raise AssertionError(
                f"parse did not reach a terminal state within {timeout_seconds:.3f}s after {attempts} polls: "
                f"lifecycle={shell['lifecycle']!r}, case_revision={shell['revision']!r}, "
                f"task_status={task['status']!r}, task_revision={task['revision']!r}"
            )
        time.sleep(min(poll_interval, remaining))


def test_submit_list_detail_task_and_source_contract(app_services):
    from app.main import app
    from app.controllers import source_controller, workbench_controller
    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services), patch.object(source_controller, "get_workbench_services", return_value=app_services):
        client = TestClient(app)
        response = client.post(
            "/api/v1/workbench/cases",
            json={"source_path": str(app_services.synthetic_report_dir), "case_name": "SYNTHETIC-CASE"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["shell"]["lifecycle"] in {"parse_queued", "parsing", "review_ready"}
        assert data["parse_task"]["status"] in {"queued", "running", "succeeded"}
        assert "internal_path" not in response.text
        case_id = data["shell"]["case_id"]
        task_id = data["parse_task"]["task_id"]
        listed = client.get("/api/v1/workbench/cases").json()["data"]
        assert listed["items"][0]["case_id"] == case_id
        detail = _wait_for_parse(client, case_id)
        assert detail["shell"]["lifecycle"] == "review_ready"
        task = client.get(f"/api/v1/workbench/tasks/{task_id}").json()["data"]
        assert task["status"] == "succeeded"
        source = client.get(f"/api/v1/workbench/sources/{detail['source']['source_id']}").json()["data"]
        assert "internal_path" not in json.dumps(source)
        assert str(app_services.synthetic_report_dir) not in response.text


def test_two_synthetic_cases_reload_independently_after_draft_edit(app_services):
    from app.main import app
    from app.controllers import workbench_controller
    from app.services.case_lifecycle_service import CaseLifecycleService

    second_report_dir = app_services.synthetic_report_dir.parent / "SYNTHETIC-SECOND-REPORT"
    shutil.copytree(app_services.synthetic_report_dir, second_report_dir)
    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
        with TestClient(app) as client:
            first = client.post(
                "/api/v1/workbench/cases",
                json={"source_path": str(app_services.synthetic_report_dir), "case_name": "SYNTHETIC-FIRST"},
            ).json()["data"]
            second = client.post(
                "/api/v1/workbench/cases",
                json={"source_path": str(second_report_dir), "case_name": "SYNTHETIC-SECOND"},
            ).json()["data"]
            assert first["shell"]["case_id"] != second["shell"]["case_id"]
            first_case_id = first["shell"]["case_id"]
            second_case_id = second["shell"]["case_id"]
            first_ready = _wait_for_parse(client, first_case_id)
            second_ready = _wait_for_parse(client, second_case_id)
            first_draft = copy.deepcopy(first_ready["draft"])
            first_draft["report"]["title"] = "SYNTHETIC-FIRST-EDIT"
            saved = app_services.lifecycle.save_draft(
                first_draft, first_draft["revision"], None, None, IDENTITY,
            )
            assert saved["draft_save_status"]["status"] == "saved"

            refreshed_first = client.get(
                f"/api/v1/workbench/cases/{first_case_id}"
            ).json()["data"]
            refreshed_second = client.get(
                f"/api/v1/workbench/cases/{second_case_id}"
            ).json()["data"]
            assert refreshed_first["draft"]["report"]["title"] == "SYNTHETIC-FIRST-EDIT"
            assert refreshed_second["draft"]["report"]["title"] == REPORT["title"]

            restarted_database = WorkbenchDatabase(
                app_services.database.database_path,
                app_services.database.deployment_instance_id,
            )
            restarted_source = SourceRecordService(
                restarted_database, app_services.sources.authorization,
            )
            restarted = WorkbenchServices(
                restarted_database,
                CaseDraftService(restarted_database, parser=lambda *_args: {"report": copy.deepcopy(REPORT)}, source_service=restarted_source),
                CaseLifecycleService(restarted_database),
                SharedDefaultsService(restarted_database),
                EditLeaseService(restarted_database),
                restarted_source,
                TaskRecordService(restarted_database),
            )

    with patch.object(workbench_controller, "get_workbench_services", return_value=restarted):
        with TestClient(app) as client:
            reloaded = client.get("/api/v1/workbench/cases").json()["data"]["items"]
            assert {item["case_id"] for item in reloaded} == {
                first_case_id, second_case_id,
            }
            reloaded_first = client.get(
                f"/api/v1/workbench/cases/{first_case_id}"
            ).json()["data"]
            reloaded_second = client.get(
                f"/api/v1/workbench/cases/{second_case_id}"
            ).json()["data"]

    assert reloaded_first["shell"]["lifecycle"] == "review_ready"
    assert reloaded_second["shell"]["lifecycle"] == "review_ready"
    assert reloaded_first["draft"]["report"]["title"] == "SYNTHETIC-FIRST-EDIT"
    assert reloaded_second["draft"]["report"]["title"] == REPORT["title"]
    assert reloaded_first["source"]["source_id"] != reloaded_second["source"]["source_id"]


def test_http_revision_conflict_and_defaults_are_stable(app_services):
    from app.main import app
    from app.controllers import workbench_controller, defaults_controller
    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services), patch.object(defaults_controller, "get_workbench_services", return_value=app_services):
        client = TestClient(app)
        detail = client.post(
            "/api/v1/workbench/cases", json={"source_path": str(app_services.synthetic_report_dir)},
        ).json()["data"]
        case_id = detail["shell"]["case_id"]
        draft = _wait_for_parse(client, case_id)["draft"]
        body = {"draft": {"report": draft["report"], "field_states": draft["field_states"], "asset_refs": [], "lifecycle": "review_ready"}, "expected_revision": 0}
        conflict = client.patch(f"/api/v1/workbench/cases/{case_id}/draft", json=body)
        assert conflict.status_code == 409
        defaults = client.get("/api/v1/workbench/defaults").json()["data"]
        saved = client.put("/api/v1/workbench/defaults", json={"values": {"document_number": "SYNTHETIC-DEFAULT"}, "expected_revision": defaults["revision"], "identity": IDENTITY})
        assert saved.status_code == 200
        assert saved.json()["data"]["document_number"] == "SYNTHETIC-DEFAULT"


def test_dispatch_failure_keeps_retryable_case_and_retry_endpoint(app_services):
    from app.main import app
    from app.controllers import workbench_controller
    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
        client = TestClient(app)
        with patch.object(
            app_services.dispatcher,
            "dispatch",
            side_effect=RuntimeError("SYNTHETIC dispatch failure"),
        ):
            response = client.post(
                "/api/v1/workbench/cases",
                json={"source_path": str(app_services.synthetic_report_dir)},
            )
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "TASK_DISPATCH_FAILED"
        listed = client.get("/api/v1/workbench/cases").json()["data"]["items"]
        assert listed[0]["lifecycle"] == "parse_failed_retryable"
        detail = client.get(f"/api/v1/workbench/cases/{listed[0]['case_id']}").json()["data"]
        assert detail["parse_task"]["status"] == "failed_retryable"
        retried = client.post(f"/api/v1/workbench/cases/{listed[0]['case_id']}/retry")
        assert retried.status_code == 200
        deadline = time.perf_counter() + 1
        lifecycle = "parse_queued"
        while time.perf_counter() < deadline:
            lifecycle = client.get(
                f"/api/v1/workbench/cases/{listed[0]['case_id']}"
            ).json()["data"]["shell"]["lifecycle"]
            if lifecycle == "review_ready":
                break
            time.sleep(0.01)
        assert lifecycle == "review_ready"


def test_empty_submission_has_stable_source_error(app_services):
    from app.main import app
    from app.controllers import workbench_controller
    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
        response = TestClient(app).post(
            "/api/v1/workbench/cases",
            json={"source_path": ""},
        )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "SOURCE_DIRECTORY_REQUIRED"


def test_submit_returns_before_slow_parse_task_finishes(app_services):
    from app.main import app
    from app.controllers import workbench_controller

    parser_started = Event()
    parser_finished = Event()

    def slow_parser(_source_path, _output_dir, **_kwargs):
        parser_started.set()
        time.sleep(0.4)
        parser_finished.set()
        return {"report": copy.deepcopy(REPORT)}

    app_services.cases.parser = slow_parser
    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
        client = TestClient(app)
        started = time.perf_counter()
        response = client.post(
            "/api/v1/workbench/cases",
            json={"source_path": str(app_services.synthetic_report_dir)},
        )
        elapsed = time.perf_counter() - started
        case_id = response.json()["data"]["shell"]["case_id"]
        assert parser_started.wait(1)
        assert not parser_finished.is_set()
        detail = _wait_for_parse(client, case_id)

    assert response.status_code == 200
    assert elapsed < 0.3
    assert parser_finished.is_set()
    assert detail["shell"]["lifecycle"] == "review_ready"


def test_wait_for_parse_times_out_with_last_state_diagnostics():
    class FakeResponse:
        def json(self):
            return {"data": {
                "shell": {"lifecycle": "parsing", "revision": 1},
                "parse_task": {"status": "running", "revision": 1},
            }}

    class FakeClient:
        def get(self, _url):
            return FakeResponse()

    with pytest.raises(AssertionError, match="lifecycle='parsing'.*task_status='running'"):
        _wait_for_parse(FakeClient(), "case-synthetic", timeout_seconds=0.02, poll_interval=0.001)


def test_submit_returns_before_slow_source_fingerprint_finishes(app_services):
    from app.main import app
    from app.controllers import workbench_controller
    from app.services import source_record_service

    original_fingerprint = source_record_service._fingerprint
    started_fingerprint = Event()
    release_fingerprint = Event()

    def slow_fingerprint(path):
        started_fingerprint.set()
        release_fingerprint.wait(1)
        return original_fingerprint(path)

    with patch.object(source_record_service, "_fingerprint", side_effect=slow_fingerprint):
        with patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
            client = TestClient(app)
            started = time.perf_counter()
            response = client.post(
                "/api/v1/workbench/cases",
                json={"source_path": str(app_services.synthetic_report_dir)},
            )
            elapsed = time.perf_counter() - started
            case_id = response.json()["data"]["shell"]["case_id"]
            assert started_fingerprint.wait(1)
            detail = _wait_for_parse(client, case_id)
            release_fingerprint.set()

    assert response.status_code == 200
    assert elapsed < 0.3
    assert detail["shell"]["lifecycle"] == "review_ready"


def test_post_parse_source_verification_failure_does_not_undo_review_ready(app_services):
    from app.main import app
    from app.controllers import workbench_controller
    from app.services import source_record_service

    with patch.object(
        source_record_service,
        "_fingerprint",
        side_effect=RuntimeError("SYNTHETIC verification failure"),
    ), patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
        client = TestClient(app)
        created = client.post(
            "/api/v1/workbench/cases",
            json={"source_path": str(app_services.synthetic_report_dir)},
        ).json()["data"]
        deadline = time.perf_counter() + 5
        detail = _wait_for_parse(client, created["shell"]["case_id"])
        while detail["source"]["access_status"] == "pending" and time.perf_counter() < deadline:
            time.sleep(0.01)
            detail = client.get(
                f"/api/v1/workbench/cases/{created['shell']['case_id']}"
            ).json()["data"]

    assert detail["shell"]["lifecycle"] == "review_ready"
    assert detail["draft"] is not None
    assert detail["source"]["access_status"] == "requires_reselection"


def test_deferred_decision_does_not_conflict_with_pending_source_verification(app_services):
    from app.main import app
    from app.controllers import workbench_controller
    from app.services import source_record_service

    original_fingerprint = source_record_service._fingerprint
    verification_started = Event()
    verification_finished = Event()
    release_verification = Event()

    def slow_fingerprint(path):
        verification_started.set()
        release_verification.wait(1)
        try:
            return original_fingerprint(path)
        finally:
            verification_finished.set()

    try:
        with patch.object(source_record_service, "_fingerprint", side_effect=slow_fingerprint), patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
            client = TestClient(app)
            created = client.post(
                "/api/v1/workbench/cases", json={"source_path": str(app_services.synthetic_report_dir)},
            ).json()["data"]
            case_id = created["shell"]["case_id"]
            ready = _wait_for_parse(client, case_id)
            assert verification_started.wait(1)
            ready_revision = ready["shell"]["revision"]
            ready_source_revision = ready["source"]["revision"]
            deferred = client.post(
                f"/api/v1/workbench/cases/{case_id}/archive-decision",
                json={"decision": "deferred", "expected_revision": ready_revision, "identity": IDENTITY},
            )
            assert deferred.status_code == 200, {
                "response": deferred.json(), "expected_revision": ready_revision,
                "current_detail": client.get(f"/api/v1/workbench/cases/{case_id}").json()["data"],
            }
            deferred_data = deferred.json()["data"]
            assert deferred_data["case"]["shell"]["revision"] == ready_revision + 1
            assert deferred_data["case"]["source"]["revision"] == ready_source_revision
            release_verification.set()
            assert verification_finished.wait(1)
            after_verification = client.get(f"/api/v1/workbench/cases/{case_id}").json()["data"]
            assert after_verification["shell"]["revision"] == ready_revision + 1
    finally:
        release_verification.set()


def test_source_change_blocks_immediate_archive_without_mutating_case_lifecycle(app_services):
    from app.main import app
    from app.controllers import workbench_controller

    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
        client = TestClient(app)
        created = client.post(
            "/api/v1/workbench/cases", json={"source_path": str(app_services.synthetic_report_dir)},
        ).json()["data"]
        case_id = created["shell"]["case_id"]
        ready = _wait_for_parse(client, case_id)
        source_deadline = time.monotonic() + 1
        while ready["source"]["access_status"] == "pending" and time.monotonic() < source_deadline:
            time.sleep(0.01)
            ready = client.get(f"/api/v1/workbench/cases/{case_id}").json()["data"]
        assert ready["source"]["access_status"] == "available"
        shutil.rmtree(app_services.synthetic_report_dir / "data")
        app_services.sources.revalidate(ready["source"]["source_id"])
        deferred = client.post(
            f"/api/v1/workbench/cases/{case_id}/archive-decision",
            json={"decision": "deferred", "expected_revision": ready["shell"]["revision"], "identity": IDENTITY},
        )
        assert deferred.status_code == 200
        deferred_data = deferred.json()["data"]
        immediate = client.post(
            f"/api/v1/workbench/cases/{case_id}/archive-decision",
            json={"decision": "immediate", "expected_revision": deferred_data["case"]["shell"]["revision"], "identity": IDENTITY},
        )

        assert immediate.status_code == 409
        assert immediate.json()["detail"]["code"] == "SOURCE_RESELECTION_REQUIRED"
        current = client.get(f"/api/v1/workbench/cases/{case_id}").json()["data"]
        assert current["shell"]["lifecycle"] == "archive_deferred"
        assert current["source"]["access_status"] == "requires_reselection"


def test_duplicate_dispatch_does_not_run_the_same_parse_task_twice(app_services):
    from app.main import app
    from app.controllers import workbench_controller

    started = Event()
    release = Event()
    calls = {"count": 0}

    def blocking_parser(_source_path, _output_dir, **_kwargs):
        calls["count"] += 1
        started.set()
        release.wait(1)
        return {"report": copy.deepcopy(REPORT)}

    app_services.cases.parser = blocking_parser
    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
        client = TestClient(app)
        response = client.post(
            "/api/v1/workbench/cases",
            json={"source_path": str(app_services.synthetic_report_dir)},
        )
        data = response.json()["data"]
        app_services.dispatcher.dispatch(
            app_services.cases, data["shell"]["case_id"], data["parse_task"]["task_id"]
        )
        assert started.wait(1)
        release.set()
        detail = _wait_for_parse(client, data["shell"]["case_id"])

    assert response.status_code == 200
    assert calls["count"] == 1
    assert detail["parse_task"]["status"] == "succeeded"


def test_unhandled_worker_exception_becomes_retryable_state(app_services):
    from app.main import app
    from app.controllers import workbench_controller

    def broken_runner(_case_id, _task_id):
        raise RuntimeError("SYNTHETIC worker failure")

    app_services.cases.run_parse_task = broken_runner
    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
        client = TestClient(app)
        response = client.post(
            "/api/v1/workbench/cases",
            json={"source_path": str(app_services.synthetic_report_dir)},
        )
        case_id = response.json()["data"]["shell"]["case_id"]
        detail = _wait_for_parse(client, case_id)

    assert response.status_code == 200
    assert detail["shell"]["lifecycle"] == "parse_failed_retryable"
    assert detail["parse_task"]["status"] == "failed_retryable"
    assert detail["parse_task"]["error_code"] == "TASK_DISPATCH_FAILED"


def test_json_source_path_route_bypasses_legacy_archive_controller(app_services):
    from fastapi.routing import APIRoute

    from app.main import app
    from app.controllers import record_controller, workbench_controller

    routes = [
        route for route in app.routes
        if isinstance(route, APIRoute)
        and route.path == "/api/v1/workbench/cases"
        and "POST" in route.methods
    ]
    assert len(routes) == 1
    assert routes[0].endpoint.__module__ == workbench_controller.__name__
    assert routes[0].endpoint is not record_controller.parse_report_endpoint

    openapi_case = app.openapi()["paths"]["/api/v1/workbench/cases"]["post"]
    assert set(openapi_case["requestBody"]["content"]) == {"application/json"}
    assert openapi_case["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/CaseSubmissionRequest"
    )

    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
        response = TestClient(app).post(
            "/api/v1/workbench/cases",
            json={"source_path": str(app_services.synthetic_report_dir)},
        )
    assert response.status_code == 200
    assert response.json()["data"]["source"]["source_type"] == "report_directory"


def test_archive_decision_endpoint_persists_deferred_and_returns_opaque_legacy_context(app_services):
    from app.main import app
    from app.controllers import workbench_controller

    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
        client = TestClient(app)
        created = client.post(
            "/api/v1/workbench/cases", json={"source_path": str(app_services.synthetic_report_dir)},
        ).json()["data"]
        case_id = created["shell"]["case_id"]
        ready = _wait_for_parse(client, case_id)
        deferred = client.post(
            f"/api/v1/workbench/cases/{case_id}/archive-decision",
            json={"decision": "deferred", "expected_revision": ready["shell"]["revision"], "identity": IDENTITY},
        )
        assert deferred.status_code == 200, {
            "response": deferred.json(), "expected_revision": ready["shell"]["revision"],
            "current_detail": client.get(f"/api/v1/workbench/cases/{case_id}").json()["data"],
        }
        deferred_data = deferred.json()["data"]
        assert deferred_data["archive_status"] == "deferred"
        assert deferred_data["case"]["shell"]["lifecycle"] == "archive_deferred"
        assert "archive_context_id" not in deferred.text or deferred_data["archive_context_id"] is None

        immediate = client.post(
            f"/api/v1/workbench/cases/{case_id}/archive-decision",
            json={
                "decision": "immediate",
                "expected_revision": deferred_data["case"]["shell"]["revision"],
                "identity": IDENTITY,
            },
        )
        assert immediate.status_code == 200
        immediate_data = immediate.json()["data"]
        assert immediate_data["archive_status"] == "legacy_explicit_ready"
        assert immediate_data["case"]["shell"]["lifecycle"] == "archive_queued"
        assert immediate_data["archive_context_id"]
        assert immediate_data["archive_attempt_id"]
        assert app_services.archive_attempts.repository.get_public(
            immediate_data["archive_attempt_id"],
        )["status"] == "accepted"
        assert str(app_services.synthetic_report_dir) not in immediate.text


def test_source_replacement_resets_draft_and_explicitly_reparses(app_services):
    from app.main import app
    from app.controllers import source_controller, workbench_controller

    replacement_dir = app_services.synthetic_report_dir.parent / "SYNTHETIC-REPLACEMENT"
    shutil.copytree(app_services.synthetic_report_dir, replacement_dir)
    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services), patch.object(source_controller, "get_workbench_services", return_value=app_services):
        client = TestClient(app)
        created = client.post(
            "/api/v1/workbench/cases", json={"source_path": str(app_services.synthetic_report_dir)},
        ).json()["data"]
        case_id = created["shell"]["case_id"]
        ready = _wait_for_parse(client, case_id)
        started = Event()
        release = Event()
        def blocked_parser(_path, _output):
            started.set()
            release.wait(5)
            return {"report": copy.deepcopy(REPORT)}
        app_services.cases.parser = blocked_parser
        response = client.post(
            f"/api/v1/workbench/cases/{case_id}/source",
            json={"source_path": str(replacement_dir), "expected_revision": ready["shell"]["revision"]},
        )
        assert response.status_code == 200
        assert response.json()["data"]["access_status"] == "pending"
        assert started.wait(2)
        reset = client.get(f"/api/v1/workbench/cases/{case_id}").json()["data"]
        assert reset["draft"] is None
        assert reset["shell"]["lifecycle"] in {"parse_queued", "parsing", "review_ready"}
        release.set()
        final = _wait_for_parse(client, case_id)
        assert final["shell"]["lifecycle"] == "review_ready"


def test_directory_validation_errors_are_stable_and_do_not_echo_path(app_services, tmp_path):
    from app.main import app
    from app.controllers import workbench_controller

    invalid_path = tmp_path / "SYNTHETIC-NOT-A-REPORT"
    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
        response = TestClient(app).post(
            "/api/v1/workbench/cases", json={"source_path": str(invalid_path)},
        )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "ARCHIVE_INPUT_PATH_INVALID"
    assert str(invalid_path) not in response.text


def test_archive_upload_is_not_a_workbench_submission_contract(app_services):
    from app.main import app
    from app.controllers import workbench_controller

    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
        response = TestClient(app).post(
            "/api/v1/workbench/cases",
            files={"archive_file": ("SYNTHETIC-TEST.zip", b"SYNTHETIC/TEST", "application/zip")},
        )
    assert response.status_code == 422
