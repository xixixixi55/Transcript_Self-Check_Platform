"""Synthetic repository and controller tests for the local inspector library."""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.controllers import inspector_controller
from app.repository.inspector_repository import (
    InspectorDataError,
    InspectorRepository,
    InspectorValidationError,
    project_case_inspector_snapshot,
    resolve_app_data_dir,
)
from app.services.inspector_service import InspectorService


def test_first_create_writes_versioned_utf8_json_and_ignores_client_id(tmp_path: Path):
    repository = InspectorRepository(tmp_path)
    record = repository.create(" 合成姓名 ", "合成单位", "合成职位", "001A")

    assert record.id
    assert record.name == "合成姓名"
    payload = json.loads((tmp_path / "inspectors.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert payload["inspectors"][0]["id"] == record.id


def test_case_snapshot_is_detached_from_later_library_updates(tmp_path: Path):
    repository = InspectorRepository(tmp_path)
    record = repository.create("SYNTHETIC-INSPECTOR", "SYNTHETIC-UNIT", "SYNTHETIC-POSITION", "SYNTHETIC-001")
    snapshot = project_case_inspector_snapshot(
        record, snapshot_id="SYNTHETIC-SNAPSHOT-1", selected_order=0,
    )
    repository.update(record.id, name="SYNTHETIC-CHANGED")

    assert snapshot == {
        "snapshot_id": "SYNTHETIC-SNAPSHOT-1", "inspector_id": record.id,
        "name": "SYNTHETIC-INSPECTOR", "unit": "SYNTHETIC-UNIT", "position": "SYNTHETIC-POSITION",
        "police_number": "SYNTHETIC-001", "selected_order": 0,
    }


def test_path_override_has_priority_and_default_windows_path_is_not_repo_path():
    override = resolve_app_data_dir({"BIJI_APP_DATA_DIR": "C:/synthetic-app-data"})
    assert str(override).endswith("synthetic-app-data")
    default = resolve_app_data_dir({"LOCALAPPDATA": "C:/SyntheticLocal"})
    assert default == Path("C:/SyntheticLocal") / "文枢" / "data"
    fallback = resolve_app_data_dir({"LOCALAPPDATA": ""})
    assert fallback != Path.cwd()
    assert "biji-zijian-platform" in str(fallback)


@pytest.mark.parametrize(
    "field_values",
    [
        ("", "合成单位", "合成职位", "001"),
        ("合成姓名", "", "合成职位", "001"),
        ("合成姓名", "合成单位", "", "001"),
        ("合成姓名", "合成单位", "合成职位", ""),
        ({}, "合成单位", "合成职位", "001"),
        (["合成姓名"], "合成单位", "合成职位", "001"),
        ("合成\n姓名", "合成单位", "合成职位", "001"),
        ("x" * 101, "合成单位", "合成职位", "001"),
    ],
)
def test_fields_reject_blank_non_text_control_and_overlong_values(tmp_path: Path, field_values):
    with pytest.raises(InspectorValidationError):
        InspectorRepository(tmp_path).create(*field_values)


def test_duplicate_fields_are_rejected_but_same_name_is_allowed(tmp_path: Path):
    repository = InspectorRepository(tmp_path)
    repository.create("合成姓名", "合成单位", "合成职位", "001")
    repository.create("合成姓名", "另一单位", "合成职位", "001")
    with pytest.raises(InspectorValidationError):
        repository.create("合成姓名", "合成单位", "合成职位", "001")


def test_crud_position_and_delete(tmp_path: Path):
    repository = InspectorRepository(tmp_path)
    first = repository.create("甲", "单位甲", "职位甲", "001")
    second = repository.create("乙", "单位乙", "职位乙", "002")
    updated = repository.update(first.id, name="甲修改", position="新职位", police_number="001A")
    assert updated.name == "甲修改"
    assert updated.position == "新职位"
    assert [item.id for item in repository.list()] == [first.id, second.id]
    repository.delete(second.id)
    assert repository.get(second.id) is None


def test_v1_disabled_record_is_loaded_as_available_with_blank_position(tmp_path: Path):
    payload = {
        "schema_version": 1,
        "inspectors": [{
            "id": "SYNTHETIC-LEGACY", "name": "合成旧人员", "unit": "合成旧单位",
            "police_number": "SYNTHETIC-OLD-001", "enabled": False,
            "created_at": "2026-01-01T00:00:00Z", "updated_at": "2026-01-01T00:00:00Z",
        }],
    }
    (tmp_path / "inspectors.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    records = InspectorRepository(tmp_path).list()

    assert len(records) == 1
    assert records[0].id == "SYNTHETIC-LEGACY"
    assert records[0].position == ""
    assert "enabled" not in records[0].__dict__


def test_v2_invalid_stored_position_is_rejected(tmp_path: Path):
    repository = InspectorRepository(tmp_path)
    repository.create("合成姓名", "合成单位", "合成职位", "001")
    payload = json.loads(repository.file_path.read_text(encoding="utf-8"))
    payload["inspectors"][0]["position"] = {"invalid": True}
    repository.file_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(InspectorDataError):
        repository.list()


def test_atomic_replace_failure_keeps_original_and_cleans_temp_file(tmp_path: Path):
    repository = InspectorRepository(tmp_path)
    repository.create("原始姓名", "合成单位", "合成职位", "001")
    original = repository.file_path.read_bytes()
    with patch("app.repository.inspector_repository.os.replace", side_effect=OSError("synthetic replace failure")):
        with pytest.raises(InspectorDataError):
            repository.create("第二姓名", "合成单位", "合成职位", "002")
    assert repository.file_path.read_bytes() == original
    assert list(tmp_path.glob(".inspectors-*.tmp")) == []


def test_data_directory_failure_is_wrapped_without_path_details(tmp_path: Path):
    data_dir = tmp_path / "not-a-directory"
    data_dir.write_text("synthetic", encoding="utf-8")
    repository = InspectorRepository(data_dir)
    with pytest.raises(InspectorDataError, match="数据写入失败") as error:
        repository.create("合成姓名", "合成单位", "合成职位", "001")
    assert str(data_dir) not in str(error.value)


def test_corrupt_json_is_not_silently_overwritten_and_backup_can_be_restored(tmp_path: Path):
    repository = InspectorRepository(tmp_path)
    first = repository.create("第一姓名", "合成单位", "合成职位", "001")
    repository.update(first.id, name="第二姓名")
    repository.file_path.write_text("{broken", encoding="utf-8")
    with pytest.raises(InspectorDataError):
        repository.create("第三姓名", "合成单位", "合成职位", "003")
    assert repository.file_path.read_text(encoding="utf-8") == "{broken"
    recovered = repository.recover_from_backup()
    assert recovered[0].name == "第一姓名"
    assert repository.get(first.id).name == "第一姓名"


def test_duplicate_or_blank_stored_ids_are_rejected(tmp_path: Path):
    repository = InspectorRepository(tmp_path)
    record = repository.create("合成姓名", "合成单位", "合成职位", "001")
    payload = json.loads(repository.file_path.read_text(encoding="utf-8"))
    payload["inspectors"].append({**payload["inspectors"][0], "id": record.id})
    repository.file_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(InspectorDataError):
        repository.list()


def test_concurrent_writes_are_serialized(tmp_path: Path):
    repository = InspectorRepository(tmp_path)

    def create(index: int):
        return repository.create(f"合成姓名{index}", "合成单位", "合成职位", str(index))

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(create, range(20)))
    records = repository.list()
    assert len(records) == 20
    assert len({item.id for item in records}) == 20


def test_inspector_controller_crud_does_not_expose_local_path(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(inspector_controller, "_service", InspectorService(InspectorRepository(tmp_path)))
    test_app = FastAPI()
    test_app.include_router(inspector_controller.router, prefix="/api/v1")
    client = TestClient(test_app)
    created = client.post("/api/v1/inspectors", json={"name": "合成姓名", "unit": "合成单位", "position": "合成职位", "police_number": "001"})
    assert created.status_code == 200
    inspector_id = created.json()["data"]["id"]
    listed = client.get("/api/v1/inspectors")
    assert listed.status_code == 200
    assert listed.json()["data"][0]["id"] == inspector_id
    changed = client.put(f"/api/v1/inspectors/{inspector_id}", json={"unit": "新合成单位"})
    assert changed.status_code == 200
    assert client.post(f"/api/v1/inspectors/{inspector_id}/status", json={"enabled": False}).status_code == 404
    missing = client.get("/api/v1/inspectors/not-found")
    assert missing.status_code == 404
    assert str(tmp_path) not in missing.text


def test_inspector_controller_hides_corrupt_file_path(tmp_path: Path, monkeypatch):
    repository = InspectorRepository(tmp_path)
    repository.file_path.write_text("{broken", encoding="utf-8")
    monkeypatch.setattr(inspector_controller, "_service", InspectorService(repository))
    test_app = FastAPI()
    test_app.include_router(inspector_controller.router, prefix="/api/v1")
    response = TestClient(test_app).get("/api/v1/inspectors")
    assert response.status_code == 500
    assert response.json()["detail"] == "检查人员数据不可读取或写入"
    assert str(tmp_path) not in response.text
