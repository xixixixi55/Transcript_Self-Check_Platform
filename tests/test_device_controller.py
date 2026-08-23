"""设备 Controller 的 SYNTHETIC/TEST HTTP 合同。"""
import json
import os
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.controllers import device_controller  # noqa: E402
from app.repository import device_config as device_config_repository  # noqa: E402


@pytest.fixture()
def client(tmp_path: Path, monkeypatch) -> TestClient:
    config_dir = tmp_path / "SYNTHETIC-DEVICE-CONTROLLER"
    config_dir.mkdir()
    config_file = config_dir / "hardware_devices.json"
    config_file.write_text(json.dumps([{
        "id": "device-SYNTHETIC-existing", "name": "SYNTHETIC EXISTING",
        "model": "SYNTHETIC-MODEL", "company": "SYNTHETIC COMPANY",
        "description": "SYNTHETIC/TEST",
    }]), encoding="utf-8")
    monkeypatch.setattr(device_config_repository, "CONFIG_DIR", str(config_dir))
    monkeypatch.setattr(device_config_repository, "CONFIG_FILE", str(config_file))
    app = FastAPI()
    app.include_router(device_controller.router, prefix="/api/v1")
    return TestClient(app)


def test_device_controller_crud_company_contract(client: TestClient):
    listed = client.get("/api/v1/devices")
    assert listed.status_code == 200
    assert listed.json()["data"][0] == {
        "id": "device-SYNTHETIC-existing", "name": "SYNTHETIC EXISTING",
        "company": "SYNTHETIC COMPANY",
    }

    missing_company = client.post("/api/v1/devices", json={
        "name": "SYNTHETIC NEW",
    })
    assert missing_company.status_code == 422
    blank_company = client.post("/api/v1/devices", json={
        "name": "SYNTHETIC NEW", "company": "   ",
    })
    assert blank_company.status_code == 422

    created = client.post("/api/v1/devices", json={
        "name": "SYNTHETIC NEW", "company": "  SYNTHETIC NEW COMPANY  ",
    })
    assert created.status_code == 200
    assert created.json()["data"]["company"] == "SYNTHETIC NEW COMPANY"

    old_client_update = client.put(
        "/api/v1/devices/device-SYNTHETIC-existing", json={"name": "SYNTHETIC RENAMED"},
    )
    assert old_client_update.status_code == 200
    assert old_client_update.json()["data"]["company"] == "SYNTHETIC COMPANY"
    assert client.put(
        "/api/v1/devices/device-SYNTHETIC-existing", json={"company": "\t"},
    ).status_code == 422
    assert client.put(
        "/api/v1/devices/device-SYNTHETIC-missing", json={"name": "SYNTHETIC X"},
    ).status_code == 404


def test_device_controller_normalizes_legacy_company(client: TestClient):
    config_file = Path(device_config_repository.CONFIG_FILE)
    config_file.write_text(json.dumps([{
        "id": "device-SYNTHETIC-legacy", "name": "SYNTHETIC LEGACY",
        "model": "SYNTHETIC-MODEL", "description": "SYNTHETIC/TEST LEGACY",
    }]), encoding="utf-8")

    response = client.get("/api/v1/devices")
    assert response.status_code == 200
    assert response.json()["data"][0]["company"] == ""
