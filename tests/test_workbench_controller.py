"""目录来源工作台案件的 HTTP 契约测试。"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
import shutil
import sys
import time
from threading import Event
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import WorkbenchDatabase, database_path_for_deployment  # noqa: E402
from app.repository.workbench_database import utc_now  # noqa: E402
from app.services.archive.archive_authorization_service import ArchiveAuthorizationService  # noqa: E402
from app.services.archive.archive_attempt_service import ArchiveAttemptService  # noqa: E402
from app.services.case_artifact_deletion_service import CaseArtifactDeletionService  # noqa: E402
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
def app_services(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from app.services.archive import archive_source_runtime_service

    monkeypatch.setattr(
        archive_source_runtime_service,
        "ARCHIVE_SOURCE_RUNTIME_STORE",
        archive_source_runtime_service.ArchiveSourceRuntimeStore(),
    )
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
    services = WorkbenchServices(database, CaseDraftService(database, parser=parser, source_service=source_service), CaseLifecycleService(database, artifact_deletion_service=CaseArtifactDeletionService(database, output_root)), SharedDefaultsService(database), EditLeaseService(database), source_service, TaskRecordService(database))
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
        app_services.defaults.patch({"inspection_place": "SYNTHETIC-PREFILL"}, 0, IDENTITY)
        response = client.post(
            "/api/v1/workbench/cases",
            json={"source_path": str(app_services.synthetic_report_dir), "case_name": "SYNTHETIC-CASE"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["shell"]["lifecycle"] in {"parse_queued", "parsing", "review_ready"}
        assert data["parse_task"]["status"] in {"queued", "running", "succeeded"}
        assert data["shared_defaults"]["inspection_place"] == "SYNTHETIC-PREFILL"
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


def test_case_detail_projects_legacy_hashlib_as_hashmyfiles(app_services):
    from app.main import app
    from app.controllers import workbench_controller

    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
        client = TestClient(app)
        created = client.post(
            "/api/v1/workbench/cases",
            json={"source_path": str(app_services.synthetic_report_dir), "case_name": "SYNTHETIC-HASH-TOOL"},
        ).json()["data"]
        case_id = created["shell"]["case_id"]
        _wait_for_parse(client, case_id)
        stored = app_services.lifecycle.drafts.get(case_id)
        stored["report"]["inspection"]["software_tools"] = [
            {"name": "WinRAR压缩管理软件", "version": "6.24"},
            {
                "category": "python_hashlib", "name": "Python hashlib", "version": "3.11.0",
                "display_name": "Python hashlib 3.11.0", "confirmation_status": "confirmed",
                "provenance": [{"source_type": "runtime"}],
            },
        ]
        app_services.lifecycle.drafts.save(stored, expected_revision=stored["revision"])

        detail = client.get(f"/api/v1/workbench/cases/{case_id}").json()["data"]
        assert detail["draft"]["report"]["inspection"]["software_tools"] == [
            {"name": "WinRAR压缩管理软件", "version": "6.24"},
            {
                "category": "hashmyfiles", "name": "HashMyFiles", "version": "2.51",
                "display_name": "HashMyFiles 2.51", "confirmation_status": "confirmed",
                "provenance": [{"source_type": "runtime"}],
            },
        ]
        persisted = app_services.lifecycle.drafts.get(case_id)
        assert persisted["report"]["inspection"]["software_tools"][1]["name"] == "Python hashlib"


def test_select_directory_endpoint_submits_selected_directory_without_exposing_path(app_services):
    from app.main import app
    from app.controllers import workbench_controller

    picker = MagicMock()
    picker.select.return_value = str(app_services.synthetic_report_dir)
    app_services.directory_picker = picker
    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
        client = TestClient(app)
        response = client.post(
            "/api/v1/workbench/cases/select-directory",
            json={"case_name": "SYNTHETIC-PICKED-CASE"},
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["shell"]["case_name"] == "SYNTHETIC-PICKED-CASE"
        assert data["source"]["source_type"] == "report_directory"
        assert str(app_services.synthetic_report_dir) not in response.text
        picker.select.assert_called_once_with(history_kind="report")
        _wait_for_parse(client, data["shell"]["case_id"])


def test_select_directory_endpoint_cancel_does_not_create_case(app_services):
    from app.main import app
    from app.controllers import workbench_controller

    picker = MagicMock()
    picker.select.return_value = None
    app_services.directory_picker = picker
    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
        client = TestClient(app)
        response = client.post("/api/v1/workbench/cases/select-directory", json={})
        assert response.status_code == 200, response.text
        assert response.json()["data"] == {"cancelled": True}
        assert client.get("/api/v1/workbench/cases").json()["data"]["items"] == []
        picker.select.assert_called_once_with(history_kind="report")


def test_delete_case_endpoint_removes_case_from_workbench(app_services):
    from app.main import app
    from app.controllers import workbench_controller

    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
        client = TestClient(app)
        created = client.post(
            "/api/v1/workbench/cases",
            json={"source_path": str(app_services.synthetic_report_dir), "case_name": "SYNTHETIC-DELETE"},
        ).json()["data"]
        case_id = created["shell"]["case_id"]
        _wait_for_parse(client, case_id)
        attempt_id = "attempt-SYNTHETIC-DELETE-ENDPOINT"
        with app_services.database.transaction() as connection:
            connection.execute(
                "INSERT INTO archive_attempts(attempt_id,schema_version,case_id,task_id,deployment_instance_id,source_id,"
                "input_revision,status,cleanup_status,created_at,revision) "
                "VALUES (?,?,?,?,?,?,?,'interrupted','pending',?,0)",
                (attempt_id, 1, case_id, "SYNTHETIC-DELETE-ARCHIVE-TASK",
                 app_services.database.deployment_instance_id, created["source"]["source_id"], 0, utc_now()),
            )
            connection.execute(
                "INSERT INTO archive_context_bindings(context_hash,attempt_id,case_id,source_id,source_revision,"
                "draft_revision,report_fingerprint,context_kind,active,expires_at,consumed_at,created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                ("SYNTHETIC-DELETE-ENDPOINT-CONTEXT", attempt_id, case_id,
                 created["source"]["source_id"], 0, 0, "SYNTHETIC-REPORT", "workbench", 1,
                 None, None, utc_now()),
            )

        response = client.delete(f"/api/v1/workbench/cases/{case_id}")

        assert response.status_code == 200, response.text
        assert response.json()["data"] == {"case_id": case_id, "deleted": True}
        listed = client.get("/api/v1/workbench/cases").json()["data"]["items"]
        assert case_id not in {item["case_id"] for item in listed}


def test_submit_accepts_external_report_directory_when_authorization_is_disabled(app_services):
    from app.main import app
    from app.controllers import workbench_controller

    external = app_services.synthetic_report_dir.parent.parent / "SYNTHETIC-EXTERNAL-ROOT" / "SYNTHETIC-REPORT"
    shutil.copytree(app_services.synthetic_report_dir, external)
    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
        response = TestClient(app).post(
            "/api/v1/workbench/cases",
            json={
                "source_path": str(external),
                "source_authorization_enabled": False,
            },
        )
    assert response.status_code == 200
    assert response.json()["data"]["source"]["source_type"] == "report_directory"


def test_two_synthetic_cases_reload_independently_after_draft_edit(app_services):
    from app.main import create_app
    from app.controllers import workbench_controller
    from app.services.case_lifecycle_service import CaseLifecycleService

    app = create_app(service_provider=lambda: app_services, enable_archive_runtime=False)
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
        cleared = client.put(
            "/api/v1/workbench/defaults",
            json={
                "values": {"document_number": "", "inspector_order": []},
                "expected_revision": saved.json()["data"]["revision"],
                "identity": IDENTITY,
            },
        )
        assert cleared.status_code == 200
        assert cleared.json()["data"]["document_number"] == ""
        assert cleared.json()["data"]["inspector_order"] == []


def test_http_draft_save_reports_shared_defaults_partial_success_and_current_revision(app_services):
    from app.main import app
    from app.controllers import defaults_controller, workbench_controller

    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services), patch.object(
        defaults_controller, "get_workbench_services", return_value=app_services
    ):
        client = TestClient(app)
        submitted = client.post(
            "/api/v1/workbench/cases",
            json={"source_path": str(app_services.synthetic_report_dir), "case_name": "SYNTHETIC-DUAL-SAVE"},
        ).json()["data"]
        case_id = submitted["shell"]["case_id"]
        before = _wait_for_parse(client, case_id)
        draft_before = before["draft"]
        defaults_before = client.get("/api/v1/workbench/defaults").json()["data"]

        stale_revision = defaults_before["revision"]
        advanced = client.put(
            "/api/v1/workbench/defaults",
            json={
                "values": {"inspection_method": "SYNTHETIC-ADVANCED"},
                "expected_revision": stale_revision,
                "identity": IDENTITY,
            },
        )
        assert advanced.status_code == 200
        current_defaults_revision = advanced.json()["data"]["revision"]

        draft_payload = copy.deepcopy(draft_before)
        draft_payload.pop("lifecycle", None)
        draft_payload["report"]["introduction"]["inspection_place"] = "SYNTHETIC-CURRENT-CASE"
        response = client.patch(
            f"/api/v1/workbench/cases/{case_id}/draft",
            json={
                "draft": draft_payload,
                "expected_revision": draft_before["revision"],
                "shared_defaults_patch": {"inspection_place": "SYNTHETIC-CURRENT-CASE"},
                "shared_defaults_revision": stale_revision,
                "identity": IDENTITY,
            },
        )

        assert response.status_code == 200
        result = response.json()["data"]
        assert result["draft_save_status"] == {
            "status": "saved",
            "revision": draft_before["revision"] + 1,
        }
        assert result["shared_defaults_save_status"] == {
            "status": "revision_conflict",
            "error_code": "REVISION_CONFLICT",
            "revision": current_defaults_revision,
        }
        assert client.get(f"/api/v1/workbench/cases/{case_id}").json()["data"]["draft"]["report"][
            "introduction"
        ]["inspection_place"] == "SYNTHETIC-CURRENT-CASE"
        defaults_after = client.get("/api/v1/workbench/defaults").json()["data"]
        assert defaults_after["inspection_place"] == ""
        assert defaults_after["revision"] == current_defaults_revision

        retry_draft = copy.deepcopy(result["draft"])
        retry_draft.pop("lifecycle", None)
        retry_draft["report"]["introduction"]["inspection_place"] = "SYNTHETIC-RETRIED-PLACE"
        retried = client.patch(
            f"/api/v1/workbench/cases/{case_id}/draft",
            json={
                "draft": retry_draft,
                "expected_revision": result["draft"]["revision"],
                "shared_defaults_patch": {"inspection_place": "SYNTHETIC-RETRIED-PLACE"},
                "shared_defaults_revision": result["shared_defaults_save_status"]["revision"],
                "identity": IDENTITY,
            },
        )
        assert retried.status_code == 200
        retried_result = retried.json()["data"]
        assert retried_result["draft_save_status"]["status"] == "saved"
        assert retried_result["shared_defaults_save_status"]["status"] == "updated"
        assert retried_result["draft"]["report"]["introduction"]["inspection_place"] == "SYNTHETIC-RETRIED-PLACE"
        assert client.get("/api/v1/workbench/defaults").json()["data"]["inspection_place"] == "SYNTHETIC-RETRIED-PLACE"

        blank_draft = copy.deepcopy(retried_result["draft"])
        blank_draft.pop("lifecycle", None)
        blank_draft["report"]["introduction"]["inspection_place"] = ""
        blank_saved = client.patch(
            f"/api/v1/workbench/cases/{case_id}/draft",
            json={
                "draft": blank_draft,
                "expected_revision": retried_result["draft"]["revision"],
                "shared_defaults_patch": {"inspection_place": "   "},
                "shared_defaults_revision": retried_result["shared_defaults_save_status"]["revision"],
                "identity": IDENTITY,
            },
        )
        assert blank_saved.status_code == 200
        blank_result = blank_saved.json()["data"]
        assert blank_result["draft"]["report"]["introduction"]["inspection_place"] == ""
        assert blank_result["shared_defaults_save_status"]["status"] == "unchanged"
        assert client.get("/api/v1/workbench/defaults").json()["data"]["inspection_place"] == "SYNTHETIC-RETRIED-PLACE"


def test_http_saved_disc_number_precedes_immediate_archive_decision(app_services):
    from app.main import app
    from app.controllers import workbench_controller
    from app.repository.archive_task_repository import ArchiveTaskRepository

    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
        client = TestClient(app)
        created = client.post(
            "/api/v1/workbench/cases",
            json={"source_path": str(app_services.synthetic_report_dir), "case_name": "SYNTHETIC-DISC-RACE"},
        ).json()["data"]
        case_id = created["shell"]["case_id"]
        ready = _wait_for_parse(client, case_id)

        draft = copy.deepcopy(ready["draft"])
        draft.pop("lifecycle", None)
        draft["report"]["attachments"]["disc_number"] = "SY20260731-001"
        saved = client.patch(
            f"/api/v1/workbench/cases/{case_id}/draft",
            json={"draft": draft, "expected_revision": ready["draft"]["revision"], "identity": IDENTITY},
        )
        assert saved.status_code == 200
        saved_detail = client.get(f"/api/v1/workbench/cases/{case_id}").json()["data"]
        assert saved_detail["draft"]["report"]["attachments"]["disc_number"] == "SY20260731-001"
        assert saved_detail["shell"]["revision"] == ready["shell"]["revision"] + 1

        expected_revision = saved_detail["shell"]["revision"]
        with patch.object(
            app_services.sources,
            "require_available",
            wraps=app_services.sources.require_available,
        ) as require_available:
            decision = client.post(
                f"/api/v1/workbench/cases/{case_id}/archive-decision",
                json={"decision": "immediate", "expected_revision": expected_revision, "identity": IDENTITY},
            )
        assert decision.status_code == 200
        assert require_available.call_count == 1
        task_id = decision.json()["data"]["archive_task"]["task_id"]
        assert ArchiveTaskRepository(app_services.database).get_current_or_recent(case_id)["task_id"] == task_id

        stale = client.post(
            f"/api/v1/workbench/cases/{case_id}/archive-decision",
            json={"decision": "immediate", "expected_revision": ready["shell"]["revision"], "identity": IDENTITY},
        )
        assert stale.status_code == 409
        assert stale.json()["detail"]["code"] in {"REVISION_CONFLICT", "ARCHIVE_TASK_ALREADY_ACTIVE"}
        assert ArchiveTaskRepository(app_services.database).get_current_or_recent(case_id)["task_id"] == task_id


def test_archive_decision_preparation_does_not_block_workbench_requests(app_services):
    from app.main import app
    from app.controllers import workbench_controller
    from app.services.archive.archive_source_runtime_service import discard_preview_source

    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
        client = TestClient(app)
        created = client.post(
            "/api/v1/workbench/cases",
            json={"source_path": str(app_services.synthetic_report_dir)},
        ).json()["data"]
        case_id = created["shell"]["case_id"]
        ready = _wait_for_parse(client, case_id)
        started = Event()
        release = Event()
        create_preview = app_services.sources.create_legacy_preview_source
        created_contexts: list[str] = []

        def delayed_preview(value: str) -> str:
            started.set()
            assert release.wait(2)
            context_id = create_preview(value)
            created_contexts.append(context_id)
            return context_id

        async def exercise() -> None:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://synthetic.test") as async_client:
                decision_task = asyncio.create_task(async_client.post(
                    f"/api/v1/workbench/cases/{case_id}/archive-decision",
                    json={"decision": "immediate", "expected_revision": ready["shell"]["revision"]},
                ))
                assert await asyncio.to_thread(started.wait, 1)
                try:
                    listed = await asyncio.wait_for(
                        async_client.get("/api/v1/workbench/cases"), timeout=0.75,
                    )
                    assert listed.status_code == 200
                finally:
                    release.set()
                decision = await decision_task
                assert decision.status_code == 200

        with patch.object(
            app_services.sources,
            "create_legacy_preview_source",
            side_effect=delayed_preview,
        ):
            asyncio.run(exercise())
        for context_id in created_contexts:
            discard_preview_source(context_id)


def test_archive_result_io_does_not_block_workbench_requests(app_services):
    from app.main import app
    from app.controllers import archive_task_controller, workbench_controller

    started = Event()
    release = Event()
    archive_api = MagicMock()

    def delayed_result(task_id: str) -> dict:
        started.set()
        assert release.wait(2)
        return {"task_id": task_id, "parts": []}

    archive_api.result.side_effect = delayed_result

    async def exercise() -> None:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://synthetic.test") as client:
            result_task = asyncio.create_task(client.get(
                "/api/v1/workbench/tasks/SYNTHETIC-SLOW-RESULT/result",
            ))
            assert await asyncio.to_thread(started.wait, 1)
            try:
                listed = await asyncio.wait_for(
                    client.get("/api/v1/workbench/cases"), timeout=0.75,
                )
                assert listed.status_code == 200
            finally:
                release.set()
            result = await result_task
            assert result.status_code == 200

    with patch.object(
        workbench_controller, "get_workbench_services", return_value=app_services,
    ), patch.object(
        archive_task_controller, "_archive_api", return_value=archive_api,
    ):
        asyncio.run(exercise())

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

    original_fingerprint = source_record_service._fingerprint_with_metadata
    started_fingerprint = Event()
    release_fingerprint = Event()

    def slow_fingerprint(path, should_cancel=None):
        started_fingerprint.set()
        release_fingerprint.wait(1)
        return original_fingerprint(path, should_cancel)

    with patch.object(source_record_service, "_fingerprint_with_metadata", side_effect=slow_fingerprint):
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
        "_fingerprint_with_metadata",
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

    original_fingerprint = source_record_service._fingerprint_with_metadata
    verification_started = Event()
    verification_finished = Event()
    release_verification = Event()

    def slow_fingerprint(path, should_cancel=None):
        verification_started.set()
        release_verification.wait(1)
        try:
            return original_fingerprint(path, should_cancel)
        finally:
            verification_finished.set()

    try:
        with patch.object(source_record_service, "_fingerprint_with_metadata", side_effect=slow_fingerprint), patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
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


def test_archive_decision_endpoint_persists_deferred_and_returns_safe_queued_task(app_services):
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
        assert immediate_data["archive_status"] == "archive_task_queued"
        assert immediate_data["case"]["shell"]["lifecycle"] == "archive_queued"
        assert immediate_data["archive_context_id"] is None
        assert immediate_data["archive_attempt_id"] is None
        assert immediate_data["archive_task"]["status"] == "queued"
        assert immediate_data["archive_task"]["allowed_actions"] == ["cancel"]
        assert str(app_services.synthetic_report_dir) not in immediate.text


def test_archive_task_list_actions_history_and_safe_projection(app_services):
    from app.main import app
    from app.controllers import workbench_controller
    from app.repository.archive_task_repository import ArchiveTaskRepository

    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
        client = TestClient(app)
        created = client.post(
            "/api/v1/workbench/cases",
            json={"source_path": str(app_services.synthetic_report_dir)},
        ).json()["data"]
        case_id = created["shell"]["case_id"]
        ready = _wait_for_parse(client, case_id)
        queued = client.post(
            f"/api/v1/workbench/cases/{case_id}/archive-decision",
            json={"decision": "immediate", "expected_revision": ready["shell"]["revision"]},
        )
        assert queued.status_code == 200

        listed = client.get("/api/v1/workbench/cases").json()["data"]["items"][0]
        summary = listed["archive_task_summary"]
        assert summary["status"] == "queued"
        assert summary["allowed_actions"] == ["cancel"]
        task_id = summary["task_id"]
        assert client.get(f"/api/v1/workbench/tasks/{task_id}/progress").json()["data"] == summary

        detail = client.get(f"/api/v1/workbench/tasks/{task_id}/details").json()["data"]
        forbidden_retry = client.post(
            f"/api/v1/workbench/tasks/{task_id}/retry",
            json={
                "expected_revision": detail["revision"],
                "expected_case_revision": listed["revision"],
            },
        )
        assert forbidden_retry.status_code == 409
        assert forbidden_retry.json()["detail"]["code"] == "ARCHIVE_RETRY_NOT_ALLOWED"
        rejected = client.post(
            f"/api/v1/workbench/tasks/{task_id}/cancel",
            json={"expected_revision": detail["revision"], "status": "succeeded"},
        )
        assert rejected.status_code == 422
        cancelled = client.post(
            f"/api/v1/workbench/tasks/{task_id}/cancel",
            json={"expected_revision": detail["revision"]},
        )
        assert cancelled.status_code == 200
        assert cancelled.json()["data"]["status"] == "cancelled"

        case = client.get(f"/api/v1/workbench/cases/{case_id}").json()["data"]["shell"]
        retried = client.post(
            f"/api/v1/workbench/tasks/{task_id}/retry",
            json={
                "expected_revision": cancelled.json()["data"]["revision"],
                "expected_case_revision": case["revision"],
            },
        )
        assert retried.status_code == 200, retried.text
        retry_data = retried.json()["data"]
        assert set(retry_data) == {"task"}
        retry_task = retry_data["task"]
        assert retry_task["task_id"] != task_id

        archive_tasks = ArchiveTaskRepository(app_services.database)
        old_attempt_id = archive_tasks.get(task_id)["process_binding"]["staging_asset_id"]
        new_attempt_id = archive_tasks.get(retry_task["task_id"])["process_binding"]["staging_asset_id"]
        assert new_attempt_id != old_attempt_id
        assert app_services.archive_attempts.repository.get_internal(new_attempt_id)["task_id"] == retry_task["task_id"]

        retry_serialized = json.dumps(retried.json(), ensure_ascii=False)
        for forbidden in (
            "archive_context_id", "archive_attempt_id", "context_hash", "fence_id",
            "lease_id", "lease_token", "owner_token", "deployment_instance_id",
            "source_id", "source_revision", "draft_revision", "report_fingerprint",
            "publication_id", "publication_digest", "process_binding", "process_tree_id",
            "staging_asset_id", "staging_locator", "ownership_marker_token",
            "internal_locator", "internal_path", "absolute_path", "raw_log",
        ):
            assert forbidden not in retry_serialized

        rejected_internal_input = client.post(
            f"/api/v1/workbench/tasks/{task_id}/retry",
            json={
                "expected_revision": cancelled.json()["data"]["revision"],
                "expected_case_revision": case["revision"],
                "archive_context_id": "SYNTHETIC-INTERNAL-CONTEXT",
                "archive_attempt_id": "SYNTHETIC-INTERNAL-ATTEMPT",
            },
        )
        assert rejected_internal_input.status_code == 422

        history = client.get(
            f"/api/v1/workbench/cases/{case_id}/archive-history",
        ).json()["data"]
        assert [item["task_id"] for item in history["items"]] == [
            retry_task["task_id"], task_id,
        ]

        serialized = json.dumps(
            client.get("/api/v1/workbench/cases").json(), ensure_ascii=False,
        )
        for forbidden in (
            "process_binding", "process_tree_id", "staging_asset_id",
            "ownership_marker_token", "process_pid", "staging_locator",
            "C:\\Users\\", "Traceback", "raw_log",
        ):
            assert forbidden not in serialized


def test_unverified_manifest_never_projects_completed_or_result(app_services):
    from app.main import app
    from app.controllers import workbench_controller
    from app.repository.archive_task_repository import ArchiveTaskRepository

    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
        client = TestClient(app)
        created = client.post(
            "/api/v1/workbench/cases",
            json={"source_path": str(app_services.synthetic_report_dir)},
        ).json()["data"]
        case_id = created["shell"]["case_id"]
        ready = _wait_for_parse(client, case_id)
        client.post(
            f"/api/v1/workbench/cases/{case_id}/archive-decision",
            json={"decision": "immediate", "expected_revision": ready["shell"]["revision"]},
        )
        tasks = ArchiveTaskRepository(app_services.database)
        task = tasks.get_current_or_recent(case_id)
        running = tasks.update_state(task["task_id"], {
            "status": "running", "worker_state": "owned_running",
        }, task["revision"])
        done = tasks.update_state(running["task_id"], {
            "status": "succeeded", "stage": "completed",
        }, running["revision"])

        listed = client.get("/api/v1/workbench/cases").json()["data"]["items"][0]
        summary = listed["archive_task_summary"]
        assert summary["status"] == "interrupted"
        assert summary["stage"] == "manifest"
        assert summary["percent"] == 95
        assert "view_result" not in summary["allowed_actions"]
        result = client.get(f"/api/v1/workbench/tasks/{done['task_id']}/result")
        assert result.status_code == 422


def test_archive_failure_detail_is_safe_and_stale_commands_conflict(app_services):
    from app.main import app
    from app.controllers import workbench_controller
    from app.repository.archive_task_repository import ArchiveTaskRepository

    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
        client = TestClient(app)
        created = client.post(
            "/api/v1/workbench/cases",
            json={"source_path": str(app_services.synthetic_report_dir)},
        ).json()["data"]
        case_id = created["shell"]["case_id"]
        ready = _wait_for_parse(client, case_id)
        client.post(
            f"/api/v1/workbench/cases/{case_id}/archive-decision",
            json={"decision": "immediate", "expected_revision": ready["shell"]["revision"]},
        )
        tasks = ArchiveTaskRepository(app_services.database)
        task = tasks.get_current_or_recent(case_id)
        running = tasks.update_state(task["task_id"], {
            "status": "running", "worker_state": "owned_running",
        }, task["revision"])
        failed = tasks.update_state(running["task_id"], {
            "status": "failed_retryable",
            "error_code": "SYNTHETIC_SAFE_CODE",
            "error_summary": "C:\\Users\\TEST\\secret.rar\nTraceback\n at worker.py:42",
        }, running["revision"])

        detail_response = client.get(
            f"/api/v1/workbench/tasks/{failed['task_id']}/details",
        )
        detail = detail_response.json()["data"]
        assert detail["error_summary"] == "[local path redacted]"
        assert detail["error_code"] == "SYNTHETIC_SAFE_CODE"
        assert "process_binding" not in detail_response.text
        stale = client.post(
            f"/api/v1/workbench/tasks/{failed['task_id']}/retry",
            json={"expected_revision": failed["revision"] - 1, "expected_case_revision": 0},
        )
        assert stale.status_code == 409


def test_archive_mapping_and_verified_result_routes(app_services):
    from app.main import app
    from app.controllers import workbench_controller
    from app.repository.archive_manifest_repository import ArchiveManifestRepository
    from app.repository.archive_plan_repository import ArchivePlanRepository
    from app.repository.archive_publish_intent_repository import ArchivePublishIntentRepository
    from app.repository.archive_task_repository import ArchiveTaskRepository

    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
        client = TestClient(app)
        created = client.post(
            "/api/v1/workbench/cases",
            json={"source_path": str(app_services.synthetic_report_dir)},
        ).json()["data"]
        case_id = created["shell"]["case_id"]
        ready = _wait_for_parse(client, case_id)
        plan = ArchivePlanRepository(app_services.database).create({
            "plan_id": "SYNTHETIC-PLAN-API",
            "case_id": case_id,
            "plan_revision": 1,
            "input_inventory_revision": 1,
            "mapping_revision": 0,
            "volume_slots": [{
                "slot_id": "SYNTHETIC-SLOT-API",
                "ordinal": 1,
                "plan_revision": 1,
                "lineage_key": "SYNTHETIC-LINEAGE",
                "planned_input_bytes": 1024,
                "status": "pending",
                "disc_mapping": None,
            }],
        })
        mapped = client.patch(
            f"/api/v1/workbench/cases/{case_id}/archive-plan",
            json={
                "expected_revision": plan["revision"],
                "mappings": [{
                    "slot_id": "SYNTHETIC-SLOT-API",
                    "disc_number": "SYNTHETIC-DISC-001",
                    "disc_date": "2026-07-30",
                    "source": "user",
                    "confirmation": "confirmed",
                }],
            },
        )
        assert mapped.status_code == 200, mapped.text
        assert mapped.json()["data"]["mapping_revision"] == 1
        assert client.get(
            f"/api/v1/workbench/cases/{case_id}/archive-plan",
        ).json()["data"]["volume_slots"][0]["disc_mapping"]["confirmation"] == "confirmed"

        context_ids = []
        original_create_preview = app_services.sources.create_legacy_preview_source

        def capture_preview(case_id_value):
            context_value = original_create_preview(case_id_value)
            context_ids.append(context_value)
            return context_value

        with patch.object(
            app_services.sources,
            "create_legacy_preview_source",
            side_effect=capture_preview,
        ):
            decision = client.post(
                f"/api/v1/workbench/cases/{case_id}/archive-decision",
                json={"decision": "immediate", "expected_revision": ready["shell"]["revision"]},
            )
        assert decision.status_code == 200
        context_id = context_ids[-1]
        tasks = ArchiveTaskRepository(app_services.database)
        task = tasks.get_current_or_recent(case_id)
        running = tasks.update_state(task["task_id"], {
            "status": "running", "worker_state": "owned_running",
        }, task["revision"])
        attempt_id = running["process_binding"]["staging_asset_id"]
        filename = "SYNTHETIC-RESULT.part1.rar"
        payload = b"SYNTHETIC-ARCHIVE-PART"
        final_dir = app_services.archive_attempts.output_root / "compressed" / "SYNTHETIC-RESULT" / "SYNTHETIC-MANIFEST-API"
        final_dir.mkdir(parents=True)
        (final_dir / filename).write_bytes(payload)
        public_manifest = {
            "manifest_id": "SYNTHETIC-MANIFEST-API",
            "archive_base_name": "SYNTHETIC-RESULT",
            "volume_size_bytes": 4_000_000_000,
            "max_part_count": 1,
            "actual_archive_bytes": len(payload),
            "validation_status": "validated",
            "parts": [{
                "part_id": "SYNTHETIC-PART-API",
                "part_number": 1,
                "filename": filename,
                "size_bytes": len(payload),
                "md5": hashlib.md5(payload).hexdigest(),
                "disc_number": "SYNTHETIC-DISC-001",
                "disc_date": "2026-07-30",
                "disc_capacity_bytes": 4_000_000_000,
                "volume_size_bytes": 4_000_000_000,
            }],
        }
        app_services.archive_attempts.persist_publish_intent(
            attempt_id,
            context_id=context_id,
            source_key="a" * 64,
            input_fingerprint="b" * 64,
            archive_fingerprint="c" * 64,
            manifest_id="SYNTHETIC-MANIFEST-API",
            final_dir=final_dir,
            target_context_id="SYNTHETIC-RESULT",
            public_manifest=public_manifest,
        )
        intent = ArchivePublishIntentRepository(app_services.database).get_for_attempt(attempt_id)
        assert intent is not None
        app_services.archive_attempts.mark_publish_phase(attempt_id, "published")
        intent = ArchivePublishIntentRepository(app_services.database).get_for_attempt(attempt_id)
        assert intent is not None
        ArchiveManifestRepository(app_services.archive_attempts.output_root).save(
            source_key="a" * 64,
            input_fingerprint="b" * 64,
            archive_fingerprint="c" * 64,
            manifest_id="SYNTHETIC-MANIFEST-API",
            final_dir=final_dir,
            workbench_attempt_id=attempt_id,
            public_manifest=public_manifest,
            publication_id=intent["publication_id"],
            publication_digest=intent["publication_digest"],
        )
        app_services.archive_attempts.mark_publish_phase(attempt_id, "indexed")
        app_services.archive_attempts.mark_publish_phase(attempt_id, "verified")
        ArchivePublishIntentRepository(app_services.database).mark_publication_state(
            attempt_id, "verified",
        )
        with app_services.database.transaction() as connection:
            connection.execute(
                "UPDATE archive_attempts SET status='succeeded',manifest_id=?,finished_at=? "
                "WHERE attempt_id=?",
                ("SYNTHETIC-MANIFEST-API", utc_now(), attempt_id),
            )
        done = tasks.update_state(running["task_id"], {
            "status": "succeeded", "stage": "completed",
        }, running["revision"])
        case_shell = client.get(f"/api/v1/workbench/cases/{case_id}").json()["data"]["shell"]
        assert case_shell["archive_task_summary"]["task_id"] == done["task_id"]
        assert case_shell["archive_task_summary"]["status"] == "succeeded"
        with patch(
            "app.services.archive.archive_manifest_service.compute_md5_streaming",
            side_effect=lambda path, _root: hashlib.md5(path.read_bytes()).hexdigest(),
        ) as compute_md5:
            result = client.get(f"/api/v1/workbench/tasks/{done['task_id']}/result")
            assert result.status_code == 200, result.text
            assert compute_md5.call_count == 0
            assert result.json()["data"]["manifest_id"] == "SYNTHETIC-MANIFEST-API"
            assert result.json()["data"]["archive_mode"] == "standard_split"
            assert result.json()["data"]["archive_medium"] == "optical_disc"
            assert result.json()["data"]["parts"][0]["part_id"] == "SYNTHETIC-PART-API"
            assert "internal_locator" not in result.text
            download = client.get(
                f"/api/v1/workbench/tasks/{done['task_id']}/result/parts/SYNTHETIC-PART-API",
            )
            assert compute_md5.call_count == 1
        assert download.status_code == 200
        assert download.content == payload
        assert filename in download.headers["content-disposition"]


def test_workbench_archive_context_requires_its_bound_attempt_but_legacy_does_not(app_services):
    from app.main import app
    from app.controllers import archive_controller, workbench_controller
    from app.services.archive.archive_execution_service import ArchiveExecutionOutcome

    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services), \
         patch.object(archive_controller, "get_workbench_services", return_value=app_services):
        client = TestClient(app)
        created = client.post(
            "/api/v1/workbench/cases",
            json={"source_path": str(app_services.synthetic_report_dir)},
        ).json()["data"]
        case_id = created["shell"]["case_id"]
        ready = _wait_for_parse(client, case_id)
        contexts: list[str] = []
        create_context = app_services.sources.create_legacy_preview_source
        with patch.object(
            app_services.sources, "create_legacy_preview_source",
            side_effect=lambda value: contexts.append(create_context(value)) or contexts[-1],
        ):
            immediate = client.post(
                f"/api/v1/workbench/cases/{case_id}/archive-decision",
                json={"decision": "immediate", "expected_revision": ready["shell"]["revision"]},
            ).json()["data"]
        task = app_services.archive_api.tasks.get_current_or_recent(case_id)
        attempt_id = task["process_binding"]["staging_asset_id"]
        context_id = contexts[0]
        manifest = {"manifest_id": "SYNTHETIC-MANIFEST-H4", "parts": []}

        with patch.object(
            archive_controller, "prepare_archive_source", return_value="SYNTHETIC-FORMAL-H4",
        ), patch.object(
            archive_controller, "execute_archive",
            return_value=ArchiveExecutionOutcome("completed", manifest["manifest_id"], None),
        ) as execute, patch.object(
            archive_controller.ARCHIVE_RUNTIME_STORE,
            "get_manifest",
            return_value=MagicMock(public_manifest=manifest),
        ), patch.object(
            archive_controller,
            "project_manifest_to_legacy_report_with_plan",
            return_value=(REPORT, None),
        ):
            omitted = client.post("/api/v1/records/archive", data={
                "archive_context_id": context_id,
                "report_json": json.dumps(REPORT, ensure_ascii=False),
            })
            assert omitted.status_code == 409
            assert omitted.json()["detail"]["code"] == "ARCHIVE_TASK_API_REQUIRED"
            execute.assert_not_called()

            wrong = client.post("/api/v1/records/archive", data={
                "archive_context_id": context_id,
                "archive_attempt_id": "attempt-SYNTHETIC-WRONG",
                "report_json": json.dumps(REPORT, ensure_ascii=False),
            })
            assert wrong.status_code == 409
            assert wrong.json()["detail"]["code"] == "ARCHIVE_TASK_API_REQUIRED"
            execute.assert_not_called()

            replaced = copy.deepcopy(REPORT)
            replaced["title"] = "SYNTHETIC/TEST/CLIENT-REPLACEMENT"
            mismatch = client.post("/api/v1/records/archive", data={
                "archive_context_id": context_id,
                "archive_attempt_id": attempt_id,
                "report_json": json.dumps(replaced, ensure_ascii=False),
            })
            assert mismatch.status_code == 409
            assert mismatch.json()["detail"]["code"] == "ARCHIVE_TASK_API_REQUIRED"
            execute.assert_not_called()

            correct = client.post("/api/v1/records/archive", data={
                "archive_context_id": context_id,
                "archive_attempt_id": attempt_id,
            })
            assert correct.status_code == 409
            assert correct.json()["detail"]["code"] == "ARCHIVE_TASK_API_REQUIRED"
            execute.assert_not_called()
            assert app_services.archive_attempts.repository.get_public(attempt_id)["status"] == "accepted"
            assert app_services.lifecycle.detail(case_id)["shell"]["lifecycle"] == "archive_queued"


def test_interrupted_archive_stays_consistent_when_context_or_attempt_creation_fails(app_services):
    from app.main import app
    from app.controllers import workbench_controller
    from app.repository.workbench_errors import WorkbenchPersistenceError
    from app.services.archive.archive_source_runtime_service import (
        ARCHIVE_SOURCE_RUNTIME_STORE,
        ArchiveRuntimeError,
    )

    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
        client = TestClient(app)
        created = client.post(
            "/api/v1/workbench/cases",
            json={"source_path": str(app_services.synthetic_report_dir)},
        ).json()["data"]
        case_id = created["shell"]["case_id"]
        ready = _wait_for_parse(client, case_id)
        initial = client.post(
            f"/api/v1/workbench/cases/{case_id}/archive-decision",
            json={"decision": "immediate", "expected_revision": ready["shell"]["revision"]},
        )
        assert initial.status_code == 200
        app_services.archive_attempts.recover_after_restart()
        interrupted = app_services.lifecycle.detail(case_id)
        before_shell = interrupted["shell"]
        before_draft = interrupted["draft"]

        with patch.object(
            app_services.sources, "create_legacy_preview_source",
            side_effect=WorkbenchPersistenceError("SYNTHETIC_CONTEXT_FAILURE"),
        ):
            failed_context = client.post(
                f"/api/v1/workbench/cases/{case_id}/archive-decision",
                json={"decision": "immediate", "expected_revision": before_shell["revision"]},
            )
        assert failed_context.status_code == 422
        after_context = app_services.lifecycle.detail(case_id)
        assert {
            key: value for key, value in after_context["shell"].items()
            if key != "archive_task_summary"
        } == {
            key: value for key, value in before_shell.items()
            if key != "archive_task_summary"
        }
        assert after_context["draft"] == before_draft

        created_context: list[str] = []
        real_create = app_services.sources.create_legacy_preview_source

        def capture_context(value: str) -> str:
            context_id = real_create(value)
            created_context.append(context_id)
            return context_id

        with patch.object(
            app_services.sources, "create_legacy_preview_source", side_effect=capture_context,
        ), patch.object(
            app_services.archive_attempts, "accept",
            side_effect=WorkbenchPersistenceError("SYNTHETIC_ATTEMPT_FAILURE"),
        ):
            failed_attempt = client.post(
                f"/api/v1/workbench/cases/{case_id}/archive-decision",
                json={"decision": "immediate", "expected_revision": before_shell["revision"]},
            )
        assert failed_attempt.status_code == 422
        assert created_context
        with pytest.raises(ArchiveRuntimeError):
            ARCHIVE_SOURCE_RUNTIME_STORE.public_summary(created_context[0])
        after_attempt = app_services.lifecycle.detail(case_id)
        assert {
            key: value for key, value in after_attempt["shell"].items()
            if key != "archive_task_summary"
        } == {
            key: value for key, value in before_shell.items()
            if key != "archive_task_summary"
        }
        assert after_attempt["draft"] == before_draft


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


def test_source_registration_errors_have_distinct_safe_messages():
    from app.controllers.source_controller import _message as source_message
    from app.controllers.workbench_controller import _message as workbench_message

    codes = (
        "ARCHIVE_INPUT_ROOT_NOT_ALLOWED",
        "SOURCE_ACCESS_DENIED",
        "SOURCE_STRUCTURE_INVALID",
    )
    initial_messages = [workbench_message(code) for code in codes]
    replacement_messages = [source_message(code) for code in codes]

    assert len(set(initial_messages)) == len(codes)
    assert len(set(replacement_messages)) == len(codes)
    assert "未获授权" in initial_messages[0]
    assert "无法访问" in initial_messages[1]
    assert "报告结构" in initial_messages[2]
    assert all("C:\\" not in message for message in initial_messages + replacement_messages)


def test_hashmyfiles_export_failures_have_safe_specific_messages():
    from app.controllers.workbench_controller import _message

    codes = [
        "HASHMYFILES_NO_PARTS", "HASHMYFILES_UNAVAILABLE",
        "HASHMYFILES_LAUNCH_FAILED", "HASHMYFILES_TIMEOUT",
        "HASHMYFILES_WINDOW_UNRESPONSIVE",
        "HASHMYFILES_RUN_FAILED", "HASHMYFILES_OUTPUT_MISSING",
        "HASHMYFILES_RESULT_INVALID", "HASHMYFILES_SCREENSHOT_FAILED",
        "HASHMYFILES_SCREENSHOT_MISSING", "HASHMYFILES_SCREENSHOT_INVALID",
    ]
    messages = [_message(code) for code in codes]
    assert all("HashMyFiles" in message for message in messages)
    assert len(messages) == len(set(messages))
    assert all(message != "工作台请求未完成，请稍后重试。" for message in messages)


def test_photo_export_failures_have_safe_actionable_messages():
    from app.controllers.workbench_controller import _message

    codes = [
        "PHOTO_ASSETS_NOT_SAVED", "ASSET_CONTENT_MISSING", "ASSET_CONTENT_CORRUPT",
        "ATTACHMENT2_IMAGE_MAPPING_INVALID", "ATTACHMENT2_MATERIAL_IMAGE_COUNT_INVALID",
        "ATTACHMENT2_IMAGE_INVALID",
    ]
    messages = [_message(code) for code in codes]
    assert all(message != "工作台请求未完成，请稍后重试。" for message in messages)
    assert "返回审核页" in messages[0]


def test_select_export_directory_endpoint_covers_selected_cancelled_and_unavailable(app_services):
    from app.main import app
    from app.controllers import workbench_controller

    picker = MagicMock()
    picker.select.return_value = str(app_services.synthetic_report_dir)
    app_services.directory_picker = picker
    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
        client = TestClient(app)
        selected = client.post("/api/v1/workbench/select-export-directory")
        picker.select.return_value = None
        cancelled = client.post("/api/v1/workbench/select-export-directory")
        app_services.directory_picker = None
        unavailable = client.post("/api/v1/workbench/select-export-directory")

    assert selected.status_code == 200, selected.text
    data = selected.json()["data"]
    assert data["path"] == str(app_services.synthetic_report_dir)
    assert isinstance(data["token"], str) and data["token"]
    assert picker.select.call_count == 2
    picker.select.assert_called_with(
        description="选择导出目录",
        history_kind="export",
        selection_validator=workbench_controller.validate_export_directory,
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["data"] == {"cancelled": True}
    assert unavailable.status_code == 422
    assert unavailable.json()["detail"]["code"] == "DIRECTORY_PICKER_UNAVAILABLE"


def test_select_export_directory_rejects_program_root_without_issuing_grant(app_services):
    from app.config import RUNTIME_PATHS
    from app.main import app
    from app.controllers import workbench_controller

    picker = MagicMock()
    picker.select.return_value = str(RUNTIME_PATHS.resource_root)
    app_services.directory_picker = picker
    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services), \
         patch.object(
             app_services.sources.authorization,
             "issue_exact_directory_grant",
             wraps=app_services.sources.authorization.issue_exact_directory_grant,
         ) as issue_grant:
        response = TestClient(app).post("/api/v1/workbench/select-export-directory")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "EXPORT_DIRECTORY_UNSAFE"
    issue_grant.assert_not_called()


def test_select_export_directory_issues_grant_for_canonical_path(app_services, tmp_path):
    from app.main import app
    from app.controllers import workbench_controller

    selected_path = str(tmp_path / "SYNTHETIC-EXPORT" / ".." / "SYNTHETIC-EXPORT")
    canonical_path = (tmp_path / "SYNTHETIC-EXPORT").resolve()
    canonical_path.mkdir()
    picker = MagicMock()
    picker.select.return_value = selected_path
    app_services.directory_picker = picker
    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services), \
         patch.object(
             workbench_controller, "validate_export_directory", return_value=canonical_path,
         ) as validate, \
         patch.object(
             app_services.sources.authorization,
             "issue_exact_directory_grant",
             return_value="token-SYNTHETIC",
         ) as issue_grant:
        response = TestClient(app).post("/api/v1/workbench/select-export-directory")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "path": str(canonical_path), "token": "token-SYNTHETIC",
    }
    picker.select.assert_called_once_with(
        description="选择导出目录",
        history_kind="export",
        selection_validator=validate,
    )
    validate.assert_called_once_with(selected_path)
    issue_grant.assert_called_once_with(str(canonical_path))
