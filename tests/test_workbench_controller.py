"""Phase 1B HTTP contract tests with synthetic uploaded archives."""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

from fastapi import BackgroundTasks
from fastapi.testclient import TestClient
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import WorkbenchDatabase, database_path_for_deployment  # noqa: E402
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
    services = WorkbenchServices(database, CaseDraftService(database, parser=parser), CaseLifecycleService(database), SharedDefaultsService(database), EditLeaseService(database), SourceRecordService(database), TaskRecordService(database))
    return services


def test_submit_list_detail_task_and_source_contract(app_services):
    from app.main import app
    from app.controllers import source_controller, workbench_controller
    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services), patch.object(source_controller, "get_workbench_services", return_value=app_services):
        client = TestClient(app)
        response = client.post("/api/v1/workbench/cases", files={"archive_file": ("SYNTHETIC-TEST.zip", b"SYNTHETIC/TEST", "application/zip")})
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["shell"]["lifecycle"] == "parse_queued"
        assert data["parse_task"]["status"] == "queued"
        assert "internal_path" not in response.text
        case_id = data["shell"]["case_id"]
        task_id = data["parse_task"]["task_id"]
        listed = client.get("/api/v1/workbench/cases").json()["data"]
        assert listed["items"][0]["case_id"] == case_id
        detail = client.get(f"/api/v1/workbench/cases/{case_id}").json()["data"]
        assert detail["shell"]["lifecycle"] == "review_ready"
        task = client.get(f"/api/v1/workbench/tasks/{task_id}").json()["data"]
        assert task["status"] == "succeeded"
        source = client.get(f"/api/v1/workbench/sources/{detail['source']['source_id']}").json()["data"]
        assert "internal_path" not in json.dumps(source)


def test_http_revision_conflict_and_defaults_are_stable(app_services):
    from app.main import app
    from app.controllers import workbench_controller, defaults_controller
    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services), patch.object(defaults_controller, "get_workbench_services", return_value=app_services):
        client = TestClient(app)
        detail = client.post("/api/v1/workbench/cases", files={"archive_file": ("SYNTHETIC-TEST.zip", b"SYNTHETIC/TEST", "application/zip")}).json()["data"]
        case_id = detail["shell"]["case_id"]
        draft = client.get(f"/api/v1/workbench/cases/{case_id}").json()["data"]["draft"]
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
        with patch.object(BackgroundTasks, "add_task", side_effect=RuntimeError("SYNTHETIC dispatch failure")):
            response = client.post(
                "/api/v1/workbench/cases",
                files={"archive_file": ("SYNTHETIC-TEST.zip", b"SYNTHETIC/TEST", "application/zip")},
            )
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "TASK_DISPATCH_FAILED"
        listed = client.get("/api/v1/workbench/cases").json()["data"]["items"]
        assert listed[0]["lifecycle"] == "parse_failed_retryable"
        detail = client.get(f"/api/v1/workbench/cases/{listed[0]['case_id']}").json()["data"]
        assert detail["parse_task"]["status"] == "failed_retryable"
        retried = client.post(f"/api/v1/workbench/cases/{listed[0]['case_id']}/retry")
        assert retried.status_code == 200
        assert client.get(f"/api/v1/workbench/cases/{listed[0]['case_id']}").json()["data"]["shell"]["lifecycle"] == "review_ready"


def test_empty_submission_has_stable_source_error(app_services):
    from app.main import app
    from app.controllers import workbench_controller
    with patch.object(workbench_controller, "get_workbench_services", return_value=app_services):
        response = TestClient(app).post(
            "/api/v1/workbench/cases",
            files={"archive_file": ("SYNTHETIC-EMPTY.zip", b"", "application/zip")},
        )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "SOURCE_EMPTY"
