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
        }, "result": {}},
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
    observe.assert_not_called()


def test_export_blocks_odd_uploaded_attachment2_images_before_docx(client):
    report = {
        "attachments": {"disc_number": "GP20260720-01", "photo_ids": []},
        "inspection": {"primary_software": {
            "name": "脱敏主取证软件",
            "version": "V1.0",
            "confirmation_status": "confirmed_by_user",
        }},
    }
    response = client.post(
        "/api/v1/records/export",
        data={"report_json": json.dumps(report, ensure_ascii=False)},
        files={"photos": ("one.png", io.BytesIO(b"not-an-image"), "image/png")},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "EXPORT_BLOCKED"
    assert detail["blockers"][0]["code"] == "ATTACHMENT2_IMAGE_COUNT_ODD"
    assert "图片数量必须为偶数" in detail["blockers"][0]["message"]
    assert "one.png" not in response.text


def test_parse_folder_compress_true(client):
    """文件夹 + compress=true → 200"""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "data"), exist_ok=True)
        resp = client.post("/api/v1/reports/parse", data={
            "report_dir": tmpdir, "compress": "true",
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["data"]["archive_context_id"]
        assert resp.json()["data"]["archive_status"] == "not_prepared"
        assert resp.json()["data"]["archive_preparation_status"] == "not_prepared"
        assert resp.json()["data"]["archive_context_deprecated_compress"] is True


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


def test_parse_folder_compress_false(client):
    """文件夹 + compress=false → 200"""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "data"), exist_ok=True)
        resp = client.post("/api/v1/reports/parse", data={
            "report_dir": tmpdir, "compress": "false",
        })
        assert resp.status_code == 200
        assert resp.json()["data"]["archive_context_id"]


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


def test_parse_rejects_unconfigured_root_and_does_not_echo_path(client):
    outside = os.environ.get("SystemRoot", r"C:\Windows")
    response = client.post("/api/v1/reports/parse", data={"report_dir": outside})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "ARCHIVE_INPUT_ROOT_NOT_ALLOWED"
    assert outside not in response.text


def test_parse_rejects_configured_root_itself(client):
    configured = Path(tempfile.gettempdir())
    root_response = client.post("/api/v1/reports/parse", data={"report_dir": str(configured)})
    assert root_response.status_code == 422
    assert root_response.json()["detail"]["code"] == "ARCHIVE_INPUT_ROOT_NOT_ALLOWED"


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


def test_parse_no_input_returns_400(client):
    """report_dir 和 archive_file 都为空 → 400"""
    resp = client.post("/api/v1/reports/parse", data={})
    assert resp.status_code == 400


def test_clear_report_parsing_cache_returns_count_and_ignores_client_path(client):
    from app.controllers import cache_controller

    with patch.object(cache_controller, "clear_report_parsing_cache", return_value=3) as clear:
        response = client.delete(
            "/api/v1/cache/report-parsing",
            params={"path": r"C:\sensitive\case"},
        )

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {"cleared_count": 3}}
    assert r"C:\sensitive\case" not in response.text
    clear.assert_called_once_with(os.path.join(cache_controller.OUTPUT_BASE, "parsed"))


def test_clear_empty_report_parsing_cache_is_idempotent(client):
    from app.controllers import cache_controller

    with patch.object(cache_controller, "clear_report_parsing_cache", return_value=0):
        response = client.delete("/api/v1/cache/report-parsing")

    assert response.status_code == 200
    assert response.json()["data"]["cleared_count"] == 0


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


def test_clear_cache_controller_offloads_file_work(client):
    from app.controllers import cache_controller

    with patch.object(cache_controller, "clear_report_parsing_cache", return_value=0) as clear_fn, \
         patch.object(cache_controller, "run_in_threadpool", new=AsyncMock(return_value=0)) as offload:
        response = client.delete("/api/v1/cache/report-parsing")

    assert response.status_code == 200
    offload.assert_awaited_once()
    assert offload.await_args.args[0] is clear_fn


def test_parse_invalid_format_returns_400(client):
    """上传非 .rar/.zip 文件 → 400"""
    fake_file = io.BytesIO(b"not an archive")
    resp = client.post("/api/v1/reports/parse", files={
        "archive_file": ("test.txt", fake_file, "text/plain"),
    })
    assert resp.status_code == 400


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
