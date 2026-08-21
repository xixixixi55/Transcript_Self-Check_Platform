"""T010: record_controller 集成测试"""
import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'packages', 'backend'))

# Mock parse_report / parse_from_archive 避免真实文件系统操作
_MOCK_REPORT = {"title": "电子数据检查笔录", "document_number": "", "introduction": {},
                "inspection": {"result": {}}, "attachments": {}}
_MOCK_RESPONSE = {
    "report": _MOCK_REPORT,
    "parsed_files": ["data_case_info.json"],
    "rar_info": {"filename": "test.rar", "md5": "a" * 32, "size_bytes": 1024, "size_display": "1.0 KB"},
      }


@pytest.fixture
def client():
    from app.main import app
    from app.controllers import record_controller
    from app.services.archive_authorization_service import ArchiveAuthorizationService

    # The test root is explicit configuration, mirroring BIJI_ALLOWED_INPUT_ROOTS.
    test_authorization = ArchiveAuthorizationService(
        tempfile.gettempdir(), record_controller.OUTPUT_BASE,
    )
    with patch("app.services.report_parser_service.parse_report",
               return_value=_MOCK_RESPONSE), \
         patch("app.services.report_parser_service.parse_from_archive",
               return_value=_MOCK_RESPONSE), \
         patch.object(record_controller, "parse_report", return_value=_MOCK_RESPONSE), \
         patch.object(record_controller, "parse_from_archive", return_value=_MOCK_RESPONSE), \
         patch.object(record_controller, "ARCHIVE_AUTHORIZATION_SERVICE", test_authorization):
        yield TestClient(app)


def test_export_rejects_non_string_disc_number_with_stable_code(client):
    report = {
        "attachments": {"disc_number": 9},
        "inspection": {"primary_software": {
            "name": "脱敏主取证软件",
            "version": "V1.0",
            "confirmation_status": "confirmed_by_user",
        }},
    }
    response = client.post(
        "/api/v1/records/export",
        data={"report_json": json.dumps(report, ensure_ascii=False)},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert [item["code"] for item in detail["blockers"]] == [
        "FIRST_DISC_NUMBER_INVALID",
    ]


def test_export_allows_report_only_word_without_archive_manifest(client, tmp_path):
    from app.controllers import record_controller

    report = {
        "title": "SYNTHETIC 电子数据检查笔录",
        "document_number": "SYN-TEST-001",
        "introduction": {"evidence_list": []},
        "inspection": {"primary_software": {
            "name": "SYNTHETIC 取证软件",
            "version": "V1.0",
            "confirmation_status": "confirmed_by_user",
        }, "result": {
            "rar_filename": "SYNTHETIC-archive.rar",
            "md5_hash": "a" * 32,
            "file_size": "1024",
        }},
        "attachments": {"disc_number": "GP20260720-01"},
    }
    docx_path = tmp_path / "SYNTHETIC-report.docx"
    docx_path.write_bytes(b"SYNTHETIC-DOCX")
    with patch.object(record_controller, "generate_docx", return_value=str(docx_path)) as generate, \
         patch.object(record_controller, "observe_shadow_export") as observe:
        response = client.post(
            "/api/v1/records/export",
            data={"report_json": json.dumps(report, ensure_ascii=False)},
        )

    assert response.status_code == 200
    assert response.content == b"SYNTHETIC-DOCX"
    assert generate.call_args.kwargs["archive_manifest"] is None
    exported_result = generate.call_args.args[0]["inspection"]["result"]
    assert {
        key: exported_result[key]
        for key in ("rar_filename", "md5_hash", "file_size")
    } == {
        "rar_filename": "SYNTHETIC-archive.rar",
        "md5_hash": "a" * 32,
        "file_size": "1024",
    }
    observe.assert_not_called()


def _directory_export_report():
    return {
        "title": "SYNTHETIC 电子数据检查笔录",
        "document_number": "SYN-TEST-DIRECTORY",
        "introduction": {"evidence_list": []},
        "inspection": {"primary_software": {
            "name": "SYNTHETIC 取证软件",
            "version": "V1.0",
            "confirmation_status": "confirmed_by_user",
        }, "result": {}},
        "attachments": {"disc_number": "GP20260812-01"},
    }


def test_word_export_allows_stale_revision_caused_only_by_late_photo_binding(client, tmp_path):
    from app.controllers import record_controller, record_template_context_controller

    submitted = _directory_export_report()
    current = json.loads(json.dumps(submitted))
    current["attachments"].update({
        "photo_ids": ["asset-SYNTHETIC-1", "asset-SYNTHETIC-2"],
        "photo_groups": [{
            "material_id": "material-SYNTHETIC-1",
            "material_number": "SYNTHETIC-JC-1",
            "display_text": "检材SYNTHETIC-JC-1照片",
            "ordered_image_ids": ["asset-SYNTHETIC-1", "asset-SYNTHETIC-2"],
            "source_order": 1,
        }],
    })
    services = MagicMock()
    services.cases.drafts.get.return_value = {
        "revision": 8, "report": current, "template_ref": None,
    }
    docx_path = tmp_path / "SYNTHETIC-photo-drift.docx"
    docx_path.write_bytes(b"SYNTHETIC-DOCX")

    with patch.object(record_template_context_controller, "get_workbench_services", return_value=services), \
         patch.object(record_controller, "resolve_case_disc_mapping") as disc_mapping, \
         patch.object(record_controller, "generate_docx", return_value=str(docx_path)) as generate:
        disc_mapping.return_value.plan_exists = False
        response = client.post("/api/v1/records/export", data={
            "report_json": json.dumps(submitted, ensure_ascii=False),
            "case_id": "case-SYNTHETIC-photo-drift", "case_revision": "7",
        })

    assert response.status_code == 200, response.text
    assert response.content == b"SYNTHETIC-DOCX"
    generate.assert_called_once()


def test_word_export_rejects_stale_revision_with_non_photo_change(client):
    from app.controllers import record_controller, record_template_context_controller

    submitted = _directory_export_report()
    current = json.loads(json.dumps(submitted))
    current["document_number"] = "SYNTHETIC-CHANGED-BY-OTHER-EDITOR"
    current["attachments"].update({
        "photo_ids": ["asset-SYNTHETIC-1", "asset-SYNTHETIC-2"],
        "photo_groups": [],
    })
    services = MagicMock()
    services.cases.drafts.get.return_value = {
        "revision": 8, "report": current, "template_ref": None,
    }

    with patch.object(record_template_context_controller, "get_workbench_services", return_value=services), \
         patch.object(record_controller, "generate_docx") as generate:
        response = client.post("/api/v1/records/export", data={
            "report_json": json.dumps(submitted, ensure_ascii=False),
            "case_id": "case-SYNTHETIC-non-photo-drift", "case_revision": "7",
        })

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "REVISION_CONFLICT"
    generate.assert_not_called()


@pytest.mark.parametrize(("case_revision", "current_photo_state"), [
    (999, {"photo_ids": ["asset-SYNTHETIC-1"], "photo_groups": []}),
    (7, {"photo_ids": [], "photo_groups": []}),
])
def test_word_export_does_not_misclassify_invalid_revision_as_late_photo_binding(
    client, case_revision, current_photo_state,
):
    from app.controllers import record_controller, record_template_context_controller

    submitted = _directory_export_report()
    current = json.loads(json.dumps(submitted))
    current["attachments"].update(current_photo_state)
    services = MagicMock()
    services.cases.drafts.get.return_value = {
        "revision": 8, "report": current, "template_ref": None,
    }

    with patch.object(record_template_context_controller, "get_workbench_services", return_value=services), \
         patch.object(record_controller, "generate_docx") as generate:
        response = client.post("/api/v1/records/export", data={
            "report_json": json.dumps(submitted, ensure_ascii=False),
            "case_id": "case-SYNTHETIC-invalid-photo-drift",
            "case_revision": str(case_revision),
        })

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "REVISION_CONFLICT"
    generate.assert_not_called()


def test_standalone_word_export_writes_to_picker_authorized_directory(client, tmp_path):
    from app.controllers import record_controller
    from app.services.archive_authorization_service import ArchiveAuthorizationService

    authorization = ArchiveAuthorizationService(tmp_path, tmp_path / "internal-output")
    token = authorization.issue_exact_directory_grant(str(tmp_path))
    services = MagicMock()
    services.sources.authorization = authorization

    def generate_to_staging(*_args, **kwargs):
        output = Path(kwargs["output_dir"]) / "SYNTHETIC-result.docx"
        output.write_bytes(b"SYNTHETIC-DIRECTORY-DOCX")
        return str(output)

    with patch.object(record_controller, "get_workbench_services", return_value=services), \
         patch.object(record_controller, "generate_docx", side_effect=generate_to_staging) as generate:
        response = client.post(
            "/api/v1/records/export",
            data={
                "report_json": json.dumps(_directory_export_report(), ensure_ascii=False),
                "export_path": str(tmp_path),
                "directory_token": token,
                "word_filename": "SYNTHETIC-result.docx",
            },
        )

    assert response.status_code == 200
    assert response.json()["data"] == {
        "export_path": str(tmp_path),
        "word_filename": "SYNTHETIC-result.docx",
    }
    assert (tmp_path / "SYNTHETIC-result.docx").read_bytes() == b"SYNTHETIC-DIRECTORY-DOCX"
    assert generate.call_args.kwargs["output_filename"] == "SYNTHETIC-result.docx"
    assert Path(generate.call_args.kwargs["output_dir"]).parent == tmp_path


def test_case_standalone_word_export_reuses_unified_export_manifest(client, tmp_path):
    from app.controllers import record_controller
    from app.services.archive_authorization_service import ArchiveAuthorizationService

    authorization = ArchiveAuthorizationService(tmp_path, tmp_path / "internal-output")
    token = authorization.issue_exact_directory_grant(str(tmp_path))
    manifest = {
        "manifest_id": "SYNTHETIC-MANIFEST",
        "validation_status": "validated",
        "volume_size_bytes": 1024,
        "parts": [{
            "part_id": "SYNTHETIC-PART-1",
            "part_number": 1,
            "filename": "SYNTHETIC-CASE.rar",
            "size_bytes": 1024,
            "md5": "a" * 32,
            "disc_number": "GP20260812-01",
            "disc_date": "2026-08-12",
            "disc_capacity_bytes": 4_700_000_000,
        }],
    }
    services = MagicMock()
    services.sources.authorization = authorization
    services.archive_api = MagicMock()
    report = _directory_export_report()
    report["introduction"]["evidence_list"] = [{
        "id": "SYNTHETIC-MATERIAL-1", "evidence_number": "SYNTHETIC-JC-1",
        "material_type": "phone", "material_type_status": "confirmed_by_user",
        "material_type_source": "user",
    }]
    report["inspection"]["software_tools"] = [
        {"name": "WinRAR压缩管理软件", "version": "7.0"},
        {"name": "HashMyFiles", "version": "2.51"},
    ]

    def generate_to_staging(*_args, **kwargs):
        output = Path(kwargs["output_dir"]) / "SYNTHETIC-result.docx"
        output.write_bytes(b"SYNTHETIC-MANIFEST-DOCX")
        return str(output)

    with patch.object(record_controller, "get_workbench_services", return_value=services), \
         patch.object(record_controller, "resolve_case_template_context", return_value={}), \
         patch.object(record_controller, "resolve_case_disc_mapping") as disc_mapping, \
         patch.object(record_controller, "resolve_case_archive_manifest", return_value=manifest) as resolve_manifest, \
         patch.object(record_controller, "generate_docx", side_effect=generate_to_staging) as generate:
        disc_mapping.return_value.plan_exists = False
        response = client.post(
            "/api/v1/records/export",
            data={
                "report_json": json.dumps(report, ensure_ascii=False),
                "case_id": "case-SYNTHETIC-export",
                "case_revision": "9",
                "export_path": str(tmp_path),
                "directory_token": token,
                "word_filename": "SYNTHETIC-result.docx",
            },
        )

    assert response.status_code == 200, response.text
    resolve_manifest.assert_called_once_with("case-SYNTHETIC-export")
    assert generate.call_args.kwargs["archive_manifest"] == manifest
    assert generate.call_args.args[0]["attachments"]["extract_list"]["rows"] == [{
        "no": "1",
        "electronic_data": "SYNTHETIC-CASE.rar",
        "source": "SYNTHETIC-JC-1检材内提取",
        "extraction_method": "使用取证设备对检材进行检查，将检出数据生成报告，然后对报告压缩并计算MD5值",
        "md5_hash": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    }]


def test_standalone_word_export_rejects_reused_or_mismatched_directory_grant(client, tmp_path):
    from app.controllers import record_controller
    from app.services.archive_authorization_service import ArchiveAuthorizationService

    selected = tmp_path / "selected"
    mismatch = tmp_path / "mismatch"
    selected.mkdir()
    mismatch.mkdir()
    authorization = ArchiveAuthorizationService(tmp_path, tmp_path / "internal-output")
    services = MagicMock()
    services.sources.authorization = authorization

    def request(token, export_path):
        return client.post(
            "/api/v1/records/export",
            data={
                "report_json": json.dumps(_directory_export_report(), ensure_ascii=False),
                "export_path": str(export_path),
                "directory_token": token,
                "word_filename": "SYNTHETIC-result.docx",
            },
        )

    with patch.object(record_controller, "get_workbench_services", return_value=services), \
         patch.object(record_controller, "generate_docx") as generate:
        mismatched = request(
            authorization.issue_exact_directory_grant(str(selected)), mismatch,
        )
        reusable_token = authorization.issue_exact_directory_grant(str(selected))
        def generate_to_staging(*_args, **kwargs):
            generated_path = Path(kwargs["output_dir"]) / "SYNTHETIC-result.docx"
            generated_path.write_bytes(b"NEW")
            return str(generated_path)
        generate.side_effect = generate_to_staging
        first = request(reusable_token, selected)
        reused = request(reusable_token, selected)

    assert mismatched.status_code == 422
    assert mismatched.json()["detail"]["code"] == "EXPORT_PATH_NOT_AUTHORIZED"
    assert first.status_code == 200
    assert (selected / "SYNTHETIC-result.docx").read_bytes() == b"NEW"
    assert reused.status_code == 422
    assert reused.json()["detail"]["code"] == "EXPORT_PATH_NOT_AUTHORIZED"
    assert generate.call_count == 1


def test_standalone_word_export_rejects_unsafe_directory_before_consuming_grant(
    client, tmp_path,
):
    from app.controllers import record_controller
    from app.repository.workbench_errors import WorkbenchPersistenceError

    services = MagicMock()
    with patch.object(record_controller, "get_workbench_services", return_value=services), \
         patch.object(
             record_controller,
             "validate_export_directory",
             side_effect=WorkbenchPersistenceError(
                 "EXPORT_DIRECTORY_UNSAFE",
                 "导出目录不能位于文枢程序或用户数据目录中，请选择其他位置。",
             ),
         ):
        response = client.post(
            "/api/v1/records/export",
            data={
                "report_json": json.dumps(_directory_export_report(), ensure_ascii=False),
                "export_path": str(tmp_path),
                "directory_token": "token-SYNTHETIC",
                "word_filename": "SYNTHETIC-result.docx",
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "EXPORT_DIRECTORY_UNSAFE"
    services.sources.authorization.consume_exact_directory_grant.assert_not_called()


def test_standalone_word_export_failure_preserves_existing_file(client, tmp_path):
    from app.controllers import record_controller
    from app.services.archive_authorization_service import ArchiveAuthorizationService

    authorization = ArchiveAuthorizationService(tmp_path, tmp_path / "internal-output")
    token = authorization.issue_exact_directory_grant(str(tmp_path))
    services = MagicMock()
    services.sources.authorization = authorization
    existing = tmp_path / "SYNTHETIC-result.docx"
    existing.write_bytes(b"PREVIOUS")

    with patch.object(record_controller, "get_workbench_services", return_value=services), \
         patch.object(record_controller, "generate_docx", side_effect=RuntimeError("private path detail")):
        response = client.post(
            "/api/v1/records/export",
            data={
                "report_json": json.dumps(_directory_export_report(), ensure_ascii=False),
                "export_path": str(tmp_path),
                "directory_token": token,
                "word_filename": "SYNTHETIC-result.docx",
            },
        )

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "DOCX_RENDER_FAILED"
    assert "private path detail" not in response.text
    assert existing.read_bytes() == b"PREVIOUS"
    assert not list(tmp_path.glob(".biji-word-export-*"))


def test_case_word_export_uses_persisted_first_disc_mapping(client, tmp_path):
    from app.controllers import record_controller, record_template_context_controller
    from app.repository import (
        ArchivePlanRepository,
        CaseShellRepository,
        WorkbenchDatabase,
        database_path_for_deployment,
    )

    report = {
        "title": "SYNTHETIC 电子数据检查笔录",
        "document_number": "SYN-TEST-MAPPED-DISC",
        "introduction": {"evidence_list": []},
        "inspection": {"primary_software": {
            "name": "SYNTHETIC 取证软件",
            "version": "V1.0",
            "confirmation_status": "confirmed_by_user",
        }, "result": {}},
        "attachments": {"disc_number": ""},
    }
    case_id = "SYNTHETIC-MAPPED-DISC-CASE"
    database = WorkbenchDatabase(
        database_path_for_deployment(tmp_path, "SYNTHETIC-MAPPED-DISC"),
        "SYNTHETIC-MAPPED-DISC",
    )
    CaseShellRepository(database).create({
        "case_id": case_id, "case_name": "SYNTHETIC/TEST/MappedDisc",
        "case_summary": "SYNTHETIC/TEST", "source_id": "SYNTHETIC-SOURCE",
        "parse_task_id": "SYNTHETIC-PARSE",
    })
    ArchivePlanRepository(database).create({
        "plan_id": "SYNTHETIC-MAPPED-DISC-PLAN", "case_id": case_id,
        "plan_revision": 1, "input_inventory_revision": 1, "mapping_revision": 1,
        "volume_slots": [{
            "slot_id": "SYNTHETIC-MAPPED-DISC-SLOT", "ordinal": 1,
            "plan_revision": 1, "lineage_key": "SYNTHETIC-LINEAGE",
            "planned_input_bytes": 1024, "status": "active",
            "disc_mapping": {
                "slot_id": "SYNTHETIC-MAPPED-DISC-SLOT",
                "disc_number": "GP20260809-01", "disc_date": "2026-08-09",
                "source": "user", "confirmation": "confirmed",
            },
        }],
    })
    docx_path = tmp_path / "SYNTHETIC-mapped-disc.docx"
    docx_path.write_bytes(b"SYNTHETIC-DOCX")
    with patch.object(record_controller, "resolve_case_template_context", return_value={}), \
         patch.object(
             record_template_context_controller, "get_workbench_services",
             return_value=MagicMock(database=database),
         ), \
         patch.object(record_controller, "generate_docx", return_value=str(docx_path)) as generate:
        response = client.post(
            "/api/v1/records/export",
            data={
                "report_json": json.dumps(report, ensure_ascii=False),
                "case_id": case_id,
                "case_revision": "7",
            },
        )

    assert response.status_code == 200
    assert generate.call_args.args[0]["attachments"]["disc_number"] == "GP20260809-01"


def test_case_word_export_rejects_pending_plan_despite_client_disc_number(client, tmp_path):
    from app.controllers import record_controller, record_template_context_controller
    from app.repository import (
        ArchivePlanRepository,
        CaseShellRepository,
        WorkbenchDatabase,
        database_path_for_deployment,
    )

    report = {
        "title": "SYNTHETIC 电子数据检查笔录",
        "document_number": "SYN-TEST-PENDING-DISC",
        "introduction": {"evidence_list": []},
        "inspection": {"primary_software": {
            "name": "SYNTHETIC 取证软件",
            "version": "V1.0",
            "confirmation_status": "confirmed_by_user",
        }, "result": {}},
        "attachments": {"disc_number": "GP20260809-99"},
    }
    case_id = "SYNTHETIC-PENDING-DISC-CASE"
    database = WorkbenchDatabase(
        database_path_for_deployment(tmp_path, "SYNTHETIC-PENDING-DISC"),
        "SYNTHETIC-PENDING-DISC",
    )
    CaseShellRepository(database).create({
        "case_id": case_id, "case_name": "SYNTHETIC/TEST/PendingDisc",
        "case_summary": "SYNTHETIC/TEST", "source_id": "SYNTHETIC-SOURCE",
        "parse_task_id": "SYNTHETIC-PARSE",
    })
    ArchivePlanRepository(database).create({
        "plan_id": "SYNTHETIC-PENDING-DISC-PLAN", "case_id": case_id,
        "plan_revision": 1, "input_inventory_revision": 1, "mapping_revision": 1,
        "volume_slots": [{
            "slot_id": "SYNTHETIC-PENDING-DISC-SLOT", "ordinal": 1,
            "plan_revision": 1, "lineage_key": "SYNTHETIC-PENDING-LINEAGE",
            "planned_input_bytes": 1024, "status": "active",
            "disc_mapping": {
                "slot_id": "SYNTHETIC-PENDING-DISC-SLOT",
                "disc_number": "GP20260809-01", "disc_date": "2026-08-09",
                "source": "user", "confirmation": "pending",
            },
        }],
    })
    with patch.object(record_controller, "resolve_case_template_context", return_value={}), \
         patch.object(
             record_template_context_controller, "get_workbench_services",
             return_value=MagicMock(database=database),
         ), \
         patch.object(record_controller, "generate_docx") as generate:
        response = client.post(
            "/api/v1/records/export",
            data={
                "report_json": json.dumps(report, ensure_ascii=False),
                "case_id": case_id,
                "case_revision": "7",
            },
        )

    assert response.status_code == 422
    assert [item["code"] for item in response.json()["detail"]["blockers"]] == [
        "FIRST_DISC_NUMBER_MISSING",
    ]
    generate.assert_not_called()


def test_directory_word_export_omits_odd_attachment2_images_without_blocking(client, tmp_path):
    from app.controllers import record_controller
    from app.services.archive_authorization_service import ArchiveAuthorizationService

    report = {
        "attachments": {"disc_number": "GP20260720-01", "photo_ids": []},
        "inspection": {"primary_software": {
            "name": "脱敏主取证软件",
            "version": "V1.0",
            "confirmation_status": "confirmed_by_user",
        }},
    }
    authorization = ArchiveAuthorizationService(tmp_path, tmp_path / "internal-output")
    token = authorization.issue_exact_directory_grant(str(tmp_path))
    services = MagicMock()
    services.sources.authorization = authorization

    def generate_to_staging(generated_report, **kwargs):
        assert generated_report["attachments"]["photo_ids"] == []
        assert generated_report["attachments"]["photo_groups"] == []
        assert kwargs["photo_paths"] == []
        output = Path(kwargs["output_dir"]) / "SYNTHETIC-no-attachment2.docx"
        output.write_bytes(b"SYNTHETIC-DOCX")
        return str(output)

    with patch.object(record_controller, "get_workbench_services", return_value=services), \
         patch.object(record_controller, "generate_docx", side_effect=generate_to_staging) as generate:
        response = client.post(
            "/api/v1/records/export",
            data={
                "report_json": json.dumps(report, ensure_ascii=False),
                "export_path": str(tmp_path),
                "directory_token": token,
                "word_filename": "SYNTHETIC-no-attachment2.docx",
            },
            files={"photos": ("pic1003.png", io.BytesIO(b"not-an-image"), "image/png")},
        )

    assert response.status_code == 200
    assert generate.call_count == 1
    assert response.json()["data"]["warnings"] == [{
        "code": "ATTACHMENT2_IMAGE_COUNT_ODD",
        "message": "当前图片不完整或无效，本次 Word 未生成附件2。",
    }]
    assert (tmp_path / "SYNTHETIC-no-attachment2.docx").read_bytes() == b"SYNTHETIC-DOCX"


def test_word_export_warns_when_material_has_no_attachment2_images(client, tmp_path):
    from app.controllers import record_controller

    report = _directory_export_report()
    report["introduction"]["evidence_list"] = [{
        "id": "material-SYNTHETIC-1",
        "evidence_number": "SYNTHETIC-JC-1",
        "material_type": "phone",
        "material_type_status": "confirmed_by_user",
        "material_type_source": "user",
    }]
    docx_path = tmp_path / "SYNTHETIC-missing-attachment2.docx"
    docx_path.write_bytes(b"SYNTHETIC-DOCX")

    with patch.object(record_controller, "generate_docx", return_value=str(docx_path)) as generate:
        response = client.post(
            "/api/v1/records/export",
            data={"report_json": json.dumps(report, ensure_ascii=False)},
        )

    assert response.status_code == 200
    assert response.headers["x-wenshu-word-warning"] == "ATTACHMENT2_IMAGE_MISSING"
    assert generate.call_args.kwargs["photo_paths"] == []
    assert generate.call_args.args[0]["attachments"]["photo_ids"] == []


def test_word_export_omits_unreadable_even_attachment2_images(client, tmp_path):
    from app.controllers import record_controller

    report = {
        "introduction": {"evidence_list": [{
            "id": "material-SYNTHETIC-1",
            "evidence_number": "SYNTHETIC-JC-1",
            "material_type": "phone",
            "material_type_status": "confirmed_by_user",
            "material_type_source": "user",
        }]},
        "attachments": {
            "disc_number": "GP20260720-01",
            "photo_ids": ["photo-1", "photo-2"],
            "photo_groups": [{
                "material_id": "material-SYNTHETIC-1",
                "material_number": "SYNTHETIC-JC-1",
                "display_text": "检材SYNTHETIC-JC-1照片",
                "ordered_image_ids": ["photo-1", "photo-2"],
                "source_order": 1,
            }],
        },
        "inspection": {"primary_software": {
            "name": "SYNTHETIC 取证软件",
            "version": "V1.0",
            "confirmation_status": "confirmed_by_user",
        }},
    }
    docx_path = tmp_path / "SYNTHETIC-unreadable-omitted.docx"
    docx_path.write_bytes(b"SYNTHETIC-DOCX")
    with patch.object(record_controller, "generate_docx", return_value=str(docx_path)) as generate:
        response = client.post(
            "/api/v1/records/export",
            data={"report_json": json.dumps(report, ensure_ascii=False)},
            files=[
                ("photos", ("pic1003.png", io.BytesIO(b"not-an-image-1"), "image/png")),
                ("photos", ("pic1005.png", io.BytesIO(b"not-an-image-2"), "image/png")),
            ],
        )

    assert response.status_code == 200
    assert generate.call_args.kwargs["photo_paths"] == []
    assert generate.call_args.args[0]["attachments"]["photo_ids"] == []
    assert response.headers["x-wenshu-word-warning"] == "ATTACHMENT2_IMAGE_INVALID"


def test_word_export_omits_attachment2_when_upload_stream_read_fails(client, tmp_path):
    from app.controllers import record_controller
    from starlette.datastructures import UploadFile as StarletteUploadFile

    report = _directory_export_report()
    report["introduction"]["evidence_list"] = [{
        "id": "material-SYNTHETIC-1",
        "evidence_number": "SYNTHETIC-JC-1",
        "material_type": "phone",
        "material_type_status": "confirmed_by_user",
        "material_type_source": "user",
    }]
    report["attachments"].update({
        "photo_ids": ["photo-1", "photo-2"],
        "photo_groups": [{
            "material_id": "material-SYNTHETIC-1",
            "material_number": "SYNTHETIC-JC-1",
            "display_text": "检材SYNTHETIC-JC-1照片",
            "ordered_image_ids": ["photo-1", "photo-2"],
            "source_order": 1,
        }],
    })
    docx_path = tmp_path / "SYNTHETIC-read-failed-omitted.docx"
    docx_path.write_bytes(b"SYNTHETIC-DOCX")

    with patch.object(StarletteUploadFile, "read", new=AsyncMock(side_effect=OSError("SYNTHETIC_READ_FAILED"))), \
         patch.object(record_controller, "generate_docx", return_value=str(docx_path)) as generate:
        response = client.post(
            "/api/v1/records/export",
            data={"report_json": json.dumps(report, ensure_ascii=False)},
            files=[
                ("photos", ("pic1003.png", io.BytesIO(b"image-1"), "image/png")),
                ("photos", ("pic1005.png", io.BytesIO(b"image-2"), "image/png")),
            ],
        )

    assert response.status_code == 200
    assert response.headers["x-wenshu-word-warning"] == "ATTACHMENT2_IMAGE_READ_FAILED"
    assert generate.call_args.kwargs["photo_paths"] == []
    assert generate.call_args.args[0]["attachments"]["photo_groups"] == []


def test_word_export_does_not_hide_attachment2_staging_write_failure(client):
    from app.controllers import record_controller

    report = _directory_export_report()
    report["introduction"]["evidence_list"] = [{
        "id": "material-SYNTHETIC-1",
        "evidence_number": "SYNTHETIC-JC-1",
        "material_type": "phone",
        "material_type_status": "confirmed_by_user",
        "material_type_source": "user",
    }]
    report["attachments"].update({
        "photo_ids": ["photo-1", "photo-2"],
        "photo_groups": [{
            "material_id": "material-SYNTHETIC-1",
            "material_number": "SYNTHETIC-JC-1",
            "display_text": "检材SYNTHETIC-JC-1照片",
            "ordered_image_ids": ["photo-1", "photo-2"],
            "source_order": 1,
        }],
    })

    with patch.object(
        record_controller,
        "open",
        create=True,
        side_effect=OSError("SYNTHETIC_STAGING_WRITE_FAILED"),
    ), patch.object(record_controller, "generate_docx") as generate:
        response = client.post(
            "/api/v1/records/export",
            data={"report_json": json.dumps(report, ensure_ascii=False)},
            files=[
                ("photos", ("pic1003.png", io.BytesIO(b"image-1"), "image/png")),
                ("photos", ("pic1005.png", io.BytesIO(b"image-2"), "image/png")),
            ],
        )

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "DOCX_RENDER_FAILED"
    generate.assert_not_called()


def test_parse_folder_accepts_deprecated_compress_values(client):
    """兼容旧 compress 参数，但两种取值都只返回待准备的预览上下文。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "data"), exist_ok=True)
        enabled = client.post("/api/v1/reports/parse", data={
            "report_dir": tmpdir, "compress": "true",
        })
        disabled = client.post("/api/v1/reports/parse", data={
            "report_dir": tmpdir, "compress": "false",
        })

        for response in (enabled, disabled):
            assert response.status_code == 200
            assert response.json()["success"] is True
            assert response.json()["data"]["archive_context_id"]
            assert response.json()["data"]["archive_status"] == "not_prepared"
            assert response.json()["data"]["archive_preparation_status"] == "not_prepared"
            assert response.json()["data"]["archive_context_deprecated_compress"] is True


def test_parse_controller_offloads_blocking_work_from_event_loop(client):
    from app.controllers import record_controller

    async def run_sync(func, *args, **kwargs):
        return func(*args, **kwargs)

    with tempfile.TemporaryDirectory() as tmpdir, \
         patch.object(record_controller, "run_in_threadpool", new=AsyncMock(side_effect=run_sync)) as offload:
        os.makedirs(os.path.join(tmpdir, "data"), exist_ok=True)
        response = client.post("/api/v1/reports/parse", data={"report_dir": tmpdir})

    assert response.status_code == 200
    called_functions = [call.args[0] for call in offload.await_args_list]
    assert record_controller.parse_report in called_functions
    assert record_controller.create_preview_source in called_functions


def test_parse_folder_returns_path_free_context_summary(client):
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "data"), exist_ok=True)
        response = client.post("/api/v1/reports/parse", data={"report_dir": tmpdir})
        assert response.status_code == 200
        data = response.json()["data"]
        assert set(data["archive_context"]) == {
            "archive_context_id", "file_count", "total_input_bytes", "status",
            "context_kind", "inventory_ready", "created_at", "expires_at",
        }
        assert data["archive_context"]["status"] == "not_prepared"
        assert data["archive_context"]["inventory_ready"] is False
        assert data["archive_context"]["file_count"] is None
        assert tmpdir not in response.text


def test_preview_parse_does_not_build_full_inventory(client):
    with tempfile.TemporaryDirectory() as tmpdir, patch(
        "app.services.archive_runtime_service.build_input_inventory",
        side_effect=AssertionError("preview must not build inventory"),
    ):
        os.makedirs(os.path.join(tmpdir, "data"), exist_ok=True)
        response = client.post("/api/v1/reports/parse", data={"report_dir": tmpdir})

    assert response.status_code == 200
    assert response.json()["data"]["archive_status"] == "not_prepared"


def test_preview_source_capacity_error_has_stable_code(client):
    from app.services.archive_runtime_service import ArchiveRuntimeError

    with tempfile.TemporaryDirectory() as tmpdir, patch(
        "app.controllers.record_controller.create_preview_source",
        side_effect=ArchiveRuntimeError("ARCHIVE_SOURCE_CAPACITY", "synthetic capacity"),
    ):
        os.makedirs(os.path.join(tmpdir, "data"), exist_ok=True)
        response = client.post("/api/v1/reports/parse", data={"report_dir": tmpdir})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "ARCHIVE_SOURCE_CAPACITY"
    assert tmpdir not in response.text


def test_parse_rejects_disallowed_roots_and_does_not_echo_paths(client):
    outside = os.environ.get("SystemRoot", r"C:\Windows")
    configured = str(Path(tempfile.gettempdir()))

    for path in (outside, configured):
        response = client.post("/api/v1/reports/parse", data={"report_dir": path})
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "ARCHIVE_INPUT_ROOT_NOT_ALLOWED"
        assert path not in response.text


def test_parse_allows_unconfigured_directory_when_authorization_is_disabled(client):
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "data"), exist_ok=True)
        response = client.post(
            "/api/v1/reports/parse",
            data={"report_dir": tmpdir, "source_authorization_enabled": "false"},
        )
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_archive_endpoint_requires_opaque_context_and_does_not_accept_client_path(client):
    response = client.post(
        "/api/v1/records/archive",
        data={
            "report_json": json.dumps(_MOCK_REPORT, ensure_ascii=False),
            "source_root": "C:\\sensitive\\case",
        },
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "ARCHIVE_CONTEXT_INVALID"
    assert "C:\\sensitive" not in response.text


def test_archive_endpoint_returns_manifest_derived_attachment1_preview(client):
    from app.services.archive_execution_service import ArchiveExecutionOutcome

    manifest = {"manifest_id": "manifest-1", "parts": []}
    preview = {"columns": [{"key": "electronic_data", "title": "电子数据"}],
               "rows": [{"electronic_data": "synthetic.rar", "md5_hash": "a" * 32}]}
    record = MagicMock(public_manifest=manifest)
    with patch("app.controllers.archive_controller.execute_archive",
               return_value=ArchiveExecutionOutcome("completed", "manifest-1", None)), \
         patch("app.controllers.archive_controller.prepare_archive_source", return_value="context-1") as prepare, \
         patch("app.controllers.archive_controller.ARCHIVE_RUNTIME_STORE.get_manifest", return_value=record), \
         patch("app.controllers.archive_controller.project_manifest_to_legacy_report_with_plan",
               return_value=({"attachments": {"extract_list": preview}}, None)):
        response = client.post("/api/v1/records/archive", data={
            "archive_context_id": "context-1",
            "report_json": json.dumps(_MOCK_REPORT, ensure_ascii=False),
        })

    assert response.status_code == 200
    assert response.json()["data"]["attachment_preview"] == preview
    prepare.assert_called_once()


def test_archive_inventory_failure_blocks_execution(client):
    from app.services.archive_runtime_service import ArchiveRuntimeError

    with patch(
        "app.controllers.archive_controller.prepare_archive_source",
        side_effect=ArchiveRuntimeError("ARCHIVE_INPUT_CHANGED", "synthetic inventory failure"),
    ), patch("app.controllers.archive_controller.execute_archive") as execute:
        response = client.post("/api/v1/records/archive", data={
            "archive_context_id": "context-1",
            "report_json": json.dumps(_MOCK_REPORT, ensure_ascii=False),
        })

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "ARCHIVE_INPUT_CHANGED"
    execute.assert_not_called()


def test_archive_status_returns_only_public_context_fields(client):
    summary = {
        "archive_context_id": "context-1", "file_count": 2,
        "total_input_bytes": 10, "status": "validating",
        "created_at": "2026-07-22T00:00:00+00:00",
        "expires_at": "2026-07-22T00:30:00+00:00",
    }
    with patch(
        "app.controllers.archive_controller.ARCHIVE_RUNTIME_STORE.get_context_summary",
        return_value=summary,
    ):
        response = client.get("/api/v1/records/archive/context-1/status")
    assert response.status_code == 200
    assert response.json()["data"] == summary
    assert "absolute" not in response.text


def test_archive_part_download_uses_opaque_ids_and_manifest_filename(client, tmp_path):
    from app.services.archive_manifest_access_service import ArchiveDownload

    part = tmp_path / "合成案件.rar"
    payload = b"synthetic-rar"
    part.write_bytes(payload)
    with patch(
        "app.controllers.archive_controller.resolve_archive_context_id",
        return_value="context-1",
    ), patch(
        "app.controllers.archive_controller.get_manifest_part_download",
        return_value=ArchiveDownload(part.name, part, len(payload)),
    ) as resolver:
        response = client.get(
            "/api/v1/records/archive/context-1/manifests/manifest-1/parts/part-1",
        )
    assert response.status_code == 200
    assert response.content == payload
    assert response.headers["content-length"] == str(len(payload))
    assert "filename*=utf-8''" in response.headers["content-disposition"].lower()
    resolver.assert_called_once_with("context-1", "manifest-1", "part-1")


def test_parse_archive_zip(client):
    """上传 .zip → 200"""
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "test.zip")
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("data/dummy.json", "{}")
        with open(zip_path, "rb") as f:
            resp = client.post("/api/v1/reports/parse", files={
                "archive_file": ("test.zip", f, "application/zip"),
            })
        assert resp.status_code == 200


def test_parse_rejects_missing_or_invalid_archive_input(client):
    missing = client.post("/api/v1/reports/parse", data={})
    invalid = client.post("/api/v1/reports/parse", files={
        "archive_file": ("test.txt", io.BytesIO(b"not an archive"), "text/plain"),
    })

    assert missing.status_code == 400
    assert "请提供 report_dir 或上传压缩包文件" in missing.json()["detail"]
    assert invalid.status_code == 400
    assert "仅支持 .rar 和 .zip" in invalid.json()["detail"]


def test_clear_report_parsing_cache_returns_count_and_ignores_client_path(client):
    from app.controllers import cache_controller

    async def run_sync(func, *args, **kwargs):
        return func(*args, **kwargs)

    with patch.object(cache_controller, "clear_report_parsing_cache", return_value=3) as clear, \
         patch.object(cache_controller, "run_in_threadpool", new=AsyncMock(side_effect=run_sync)) as offload:
        response = client.delete(
            "/api/v1/cache/report-parsing",
            params={"path": r"C:\sensitive\case"},
        )

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {"cleared_count": 3}}
    assert r"C:\sensitive\case" not in response.text
    clear.assert_called_once_with(os.path.join(cache_controller.OUTPUT_BASE, "parsed"))
    offload.assert_awaited_once()
    assert offload.await_args.args[0] is clear


def test_clear_report_parsing_cache_failure_is_not_reported_as_success(client):
    from app.controllers import cache_controller
    from app.services.report_parsing_cache_service import ReportParsingCacheError

    with patch.object(
        cache_controller,
        "clear_report_parsing_cache",
        side_effect=ReportParsingCacheError("private storage detail"),
    ):
        response = client.delete("/api/v1/cache/report-parsing")

    assert response.status_code == 500
    assert response.json()["detail"] == {
        "code": "REPORT_PARSING_CACHE_CLEAR_FAILED",
        "message": "解析缓存清理失败，请稍后重试。",
    }
    assert "private storage detail" not in response.text


def test_parse_structure_error_returns_safe_422(client):
    with tempfile.TemporaryDirectory() as tmpdir:
        error_path = os.path.join(tmpdir, "data_case_info.json")
        with patch(
            "app.controllers.record_controller.parse_report",
            side_effect=ValueError(f"invalid report at {error_path}"),
        ):
            resp = client.post("/api/v1/reports/parse", data={"report_dir": tmpdir})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "报告解析失败" in detail
    assert tmpdir not in detail
    assert "data_case_info.json" not in detail


def test_export_blocks_each_unconfirmed_material_with_stable_field_path(client):
    report = {
        "introduction": {
            "evidence_list": [
                {
                    "id": "material-1",
                    "device_type": "手机",
                    "material_type": "phone",
                    "material_type_status": "confirmed_by_report",
                    "material_type_source": "report",
                },
                {
                    "id": "material-2",
                    "device_type": "未知设备",
                    "material_type": "unconfirmed",
                    "material_type_status": "unconfirmed",
                    "material_type_source": "report",
                },
            ]
        }
    }
    response = client.post(
        "/api/v1/records/export",
        data={"report_json": json.dumps(report, ensure_ascii=False)},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "EXPORT_BLOCKED"
    assert [item["code"] for item in detail["blockers"]] == [
        "MATERIAL_TYPE_UNCONFIRMED",
        "PRIMARY_SOFTWARE_UNCONFIRMED",
        "FIRST_DISC_NUMBER_MISSING",
    ]
    assert detail["blockers"][0] == {
        "code": "MATERIAL_TYPE_UNCONFIRMED",
        "field": "introduction.evidence_list[id=material-2].material_type",
        "message": "检材类型必须先确认手机或平板。",
    }
