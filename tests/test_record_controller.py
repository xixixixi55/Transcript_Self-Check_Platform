"""T010: record_controller 集成测试"""
import io
import json
import os
import sys
import tempfile
import zipfile
from unittest.mock import patch, MagicMock
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
    with patch("app.services.report_parser_service.parse_report",
               return_value=_MOCK_RESPONSE), \
         patch("app.services.report_parser_service.parse_from_archive",
               return_value=_MOCK_RESPONSE):
        from app.main import app
        yield TestClient(app)


def test_parse_folder_compress_true(client):
    """文件夹 + compress=true → 200"""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "data"), exist_ok=True)
        resp = client.post("/api/v1/reports/parse", data={
            "report_dir": tmpdir, "compress": "true",
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is True


def test_parse_folder_compress_false(client):
    """文件夹 + compress=false → 200"""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "data"), exist_ok=True)
        resp = client.post("/api/v1/reports/parse", data={
            "report_dir": tmpdir, "compress": "false",
        })
        assert resp.status_code == 200


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
    assert detail["blockers"] == [{
        "code": "MATERIAL_TYPE_UNCONFIRMED",
        "field": "introduction.evidence_list[id=material-2].material_type",
        "message": "检材类型必须先确认手机或平板。",
    }]
