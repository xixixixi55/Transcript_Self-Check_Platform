"""T019 public template API and formal generation integration tests."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.workbench_database import WorkbenchDatabase  # noqa: E402
from app.services.template_profile_service import (  # noqa: E402
    CURRENT_TEMPLATE_PACKAGE_FINGERPRINT,
    CURRENT_TEMPLATE_VALIDATION_RULE,
    TemplateProfileError,
)
from app.services.workbench_factory_service import build_workbench_services  # noqa: E402
from test_legacy_report_projection_service import _report  # noqa: E402

CASE_ID = "case-SYNTHETIC-template-api"
REFERENCE = {"template_id": "electronic-inspection-record", "version": "1.0.0"}
IDENTITY = {
    "identity_kind": "local_session",
    "client_instance_id": "SYNTHETIC-TEMPLATE-CLIENT",
    "session_id": "SYNTHETIC-TEMPLATE-SESSION",
    "deployment_instance_id": "SYNTHETIC-TEMPLATE-API",
}


@pytest.fixture()
def template_api(tmp_path: Path):
    from app.main import app
    from app.controllers import record_template_context_controller, template_controller

    database = WorkbenchDatabase(
        tmp_path / "workbench.sqlite3", IDENTITY["deployment_instance_id"],
    )
    services = build_workbench_services(database)
    report = _report()
    report["inspection"].pop("primary_software", None)
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO case_shells(case_id,schema_version,case_number,case_name,case_summary,"
            "source_id,parse_task_id,lifecycle,report_available,revision,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                CASE_ID, 1, "SYNTHETIC-001", "SYNTHETIC template API case",
                "SYNTHETIC summary", "source-SYNTHETIC-template-api",
                "task-SYNTHETIC-template-api", "review_ready", 1, 4,
                "2026-07-30T00:00:00+00:00", "2026-07-30T00:00:00+00:00",
            ),
        )
        connection.execute(
            "INSERT INTO case_drafts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                CASE_ID, 1, json.dumps(report), "legacy-v1", "{}", "[]", None,
                "plan-SYNTHETIC-stable", "review_ready", 4,
                "2026-07-30T00:00:00+00:00", "2026-07-30T00:00:00+00:00",
            ),
        )
    lease = services.leases.acquire(CASE_ID, IDENTITY)
    with patch.object(template_controller, "get_workbench_services", return_value=services), \
         patch.object(
             record_template_context_controller,
             "get_workbench_services",
             return_value=services,
         ):
        yield TestClient(app), services, lease


def _selection_body(lease: dict, revision: int = 4) -> dict:
    return {
        "template_ref": REFERENCE,
        "expected_revision": revision,
        "lease_id": lease["lease_id"],
        "lease_token": lease["lease_token"],
    }


def _export_report() -> dict:
    return {
        "title": "SYNTHETIC 电子数据检查笔录",
        "document_number": "SYN-TEST-019",
        "introduction": {"evidence_list": []},
        "inspection": {
            "primary_software": {
                "name": "SYNTHETIC 取证软件",
                "version": "V1.0",
                "confirmation_status": "confirmed_by_user",
            },
            "result": {},
        },
        "attachments": {"disc_number": "GP20260730-01"},
    }


def test_public_list_and_selection_are_safe_and_preserve_archive_facts(template_api):
    client, services, lease = template_api
    response = client.get("/api/v1/workbench/templates")
    assert response.status_code == 200, response.text
    templates = response.json()["data"]
    assert [item["template_ref"] for item in templates] == [REFERENCE]
    assert templates[0]["approval_record"]["status"] == "approved"
    assert "internal_locator" not in response.text
    assert str(services.database.database_path.parent) not in response.text

    with services.database.connect() as connection:
        before = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("task_records", "archive_attempts", "archive_plans", "archive_assets")
        }
    response = client.put(
        f"/api/v1/workbench/cases/{CASE_ID}/template",
        json=_selection_body(lease),
    )
    assert response.status_code == 200, response.text
    result = response.json()["data"]
    assert result["draft"]["template_ref"] == REFERENCE
    assert result["draft"]["revision"] == 5
    assert result["draft"]["archive_plan_id"] == "plan-SYNTHETIC-stable"
    assert result["impact"] == {
        "word_artifact_validity": "invalidated_by_template_change",
        "archive_plan_changed": False,
        "archive_task_created": False,
        "manifest_changed": False,
        "disc_mapping_changed": False,
    }
    with services.database.connect() as connection:
        after = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in before
        }
    assert after == before


def test_selection_rejects_client_governance_fields_lease_and_stale_revision(template_api):
    client, services, lease = template_api
    body = _selection_body(lease)
    body["fingerprint"] = "sha256:SYNTHETIC-forbidden"
    assert client.put(
        f"/api/v1/workbench/cases/{CASE_ID}/template", json=body,
    ).status_code == 422

    unknown = _selection_body(lease)
    unknown["template_ref"] = {
        "template_id": "template-SYNTHETIC-unknown", "version": "9.9.9",
    }
    response = client.put(
        f"/api/v1/workbench/cases/{CASE_ID}/template", json=unknown,
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "TEMPLATE_UNKNOWN"

    assets = services.database.database_path.parent / "template-assets"
    assets.mkdir(exist_ok=True)
    pending_asset = assets / "SYNTHETIC-pending.docx"
    shutil.copy2(Path(__file__).parents[1] / "word_templates" / "template.docx", pending_asset)
    pending_ref = {"template_id": "template-SYNTHETIC-pending", "version": "1.0.0"}
    services.template_registry.register({
        "schema_version": 1,
        "template_ref": pending_ref,
        "display_name": "SYNTHETIC pending template",
        "fingerprint": CURRENT_TEMPLATE_PACKAGE_FINGERPRINT,
        "validation_rules": [CURRENT_TEMPLATE_VALIDATION_RULE],
        "asset_id": "asset-SYNTHETIC-pending",
        "registered_at": "2026-07-30T00:00:00+00:00",
    }, pending_asset)
    services.template_approvals.record(pending_ref, {
        "approval_record_id": "approval-SYNTHETIC-pending",
        "status": "pending",
        "acceptance_summary": "SYNTHETIC pending",
        "recorded_at": "2026-07-30T01:00:00+00:00",
    })
    pending = _selection_body(lease)
    pending["template_ref"] = pending_ref
    response = client.put(
        f"/api/v1/workbench/cases/{CASE_ID}/template", json=pending,
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "TEMPLATE_NOT_APPROVED"

    invalid_lease = _selection_body(lease)
    invalid_lease["lease_token"] = "token-SYNTHETIC-invalid"
    response = client.put(
        f"/api/v1/workbench/cases/{CASE_ID}/template", json=invalid_lease,
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "LEASE_NOT_ACTIVE"

    assert client.put(
        f"/api/v1/workbench/cases/{CASE_ID}/template",
        json=_selection_body(lease),
    ).status_code == 200
    response = client.put(
        f"/api/v1/workbench/cases/{CASE_ID}/template",
        json=_selection_body(lease),
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "REVISION_CONFLICT"
    assert str(client) not in response.text


def test_formal_export_resolves_server_reference_and_safely_revalidates(
    template_api, tmp_path: Path,
):
    from app.controllers import record_controller

    client, services, lease = template_api
    selection = client.put(
        f"/api/v1/workbench/cases/{CASE_ID}/template",
        json=_selection_body(lease),
    )
    revision = selection.json()["data"]["draft"]["revision"]
    output = tmp_path / "SYNTHETIC-T019.docx"
    output.write_bytes(b"SYNTHETIC-DOCX")
    with patch.object(record_controller, "generate_docx", return_value=str(output)) as generate:
        response = client.post(
            "/api/v1/records/export",
            data={
                "report_json": json.dumps(_export_report()),
                "case_id": CASE_ID,
                "case_revision": str(revision),
            },
        )
    assert response.status_code == 200
    assert generate.call_args.kwargs["template_ref"] == REFERENCE
    assert generate.call_args.kwargs["template_registry"] is services.template_registry
    assert generate.call_args.kwargs["template_approvals"] is services.template_approvals

    failure = TemplateProfileError(
        "所选模板指纹校验失败。", "TEMPLATE_FINGERPRINT_MISMATCH",
    )
    with patch.object(record_controller, "generate_docx", side_effect=failure):
        response = client.post(
            "/api/v1/records/export",
            data={
                "report_json": json.dumps(_export_report()),
                "case_id": CASE_ID,
                "case_revision": str(revision),
            },
        )
    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "TEMPLATE_FINGERPRINT_MISMATCH",
        "message": "所选模板指纹校验失败。",
    }
    assert str(services.database.database_path.parent) not in response.text
