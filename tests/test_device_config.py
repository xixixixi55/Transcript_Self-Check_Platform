"""设备配置存取与公司解析测试；全部配置写入临时 SYNTHETIC/TEST 文件。"""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'packages', 'backend'))

from app.repository.inspection import device_config as device_config_repository  # noqa: E402
from app.services.inspection.device_config_service import (  # noqa: E402
    DeviceConfigError,
    add_device,
    company_for_device_name,
    delete_device,
    list_devices,
    update_device,
)


@pytest.fixture(autouse=True)
def isolated_device_config(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "SYNTHETIC-DEVICE-CONFIG"
    monkeypatch.setattr(device_config_repository, "CONFIG_DIR", str(config_dir))
    monkeypatch.setattr(device_config_repository, "CONFIG_FILE", str(config_dir / "hardware_devices.json"))
    monkeypatch.setattr(device_config_repository, "LEGACY_CONFIG_FILE", None)


def test_list_default_devices_includes_company():
    devices = list_devices()
    assert len(devices) == 1
    assert devices[0]["company"] == "美亚柏科"
    assert set(devices[0]) == {"id", "name", "company"}


def test_legacy_device_without_company_is_normalized(tmp_path: Path):
    config_file = Path(device_config_repository.CONFIG_FILE)
    config_file.parent.mkdir(parents=True)
    config_file.write_text(json.dumps([{
        "id": "device-SYNTHETIC-legacy", "name": "SYNTHETIC LEGACY",
        "model": "SYNTHETIC-MODEL", "description": "SYNTHETIC/TEST",
    }]), encoding="utf-8")

    assert list_devices()[0] == {
        "id": "device-SYNTHETIC-legacy", "name": "SYNTHETIC LEGACY", "company": "",
    }


def test_legacy_program_config_migrates_once_to_user_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    legacy_file = tmp_path / "SYNTHETIC-PROGRAM" / "hardware_devices.json"
    legacy_file.parent.mkdir(parents=True)
    legacy_payload = [{
        "id": "device-SYNTHETIC-legacy", "name": "SYNTHETIC Legacy",
        "company": "SYNTHETIC Company", "obsolete": "SYNTHETIC",
    }]
    legacy_file.write_text(json.dumps(legacy_payload), encoding="utf-8")
    monkeypatch.setattr(device_config_repository, "LEGACY_CONFIG_FILE", str(legacy_file))

    assert list_devices() == [{
        "id": "device-SYNTHETIC-legacy", "name": "SYNTHETIC Legacy",
        "company": "SYNTHETIC Company",
    }]
    migrated = json.loads(Path(device_config_repository.CONFIG_FILE).read_text(encoding="utf-8"))
    assert migrated == list_devices()
    assert json.loads(legacy_file.read_text(encoding="utf-8")) == legacy_payload


def test_user_data_config_wins_and_mutations_do_not_touch_legacy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    legacy_file = tmp_path / "SYNTHETIC-PROGRAM" / "hardware_devices.json"
    legacy_file.parent.mkdir(parents=True)
    legacy_text = json.dumps([{
        "id": "device-SYNTHETIC-legacy", "name": "SYNTHETIC Legacy",
        "company": "SYNTHETIC Legacy Company",
    }])
    legacy_file.write_text(legacy_text, encoding="utf-8")
    monkeypatch.setattr(device_config_repository, "LEGACY_CONFIG_FILE", str(legacy_file))
    config_file = Path(device_config_repository.CONFIG_FILE)
    config_file.parent.mkdir(parents=True)
    config_file.write_text(json.dumps([{
        "id": "device-SYNTHETIC-user", "name": "SYNTHETIC User",
        "company": "SYNTHETIC User Company",
    }]), encoding="utf-8")

    assert list_devices()[0]["id"] == "device-SYNTHETIC-user"
    added = add_device("SYNTHETIC Added", "SYNTHETIC Added Company")
    update_device(added["id"], company="SYNTHETIC Updated Company")
    delete_device(added["id"])
    assert legacy_file.read_text(encoding="utf-8") == legacy_text


def test_add_update_and_delete_device_preserve_company():
    device = add_device("  SYNTHETIC Device  ", "  SYNTHETIC Company  ")
    assert device == {
        "id": device["id"], "name": "SYNTHETIC Device", "company": "SYNTHETIC Company",
    }

    updated = update_device(device["id"], name="SYNTHETIC Updated")
    assert updated["name"] == "SYNTHETIC Updated"
    assert updated["company"] == "SYNTHETIC Company"
    changed_company = update_device(device["id"], company="SYNTHETIC New Company")
    assert changed_company["company"] == "SYNTHETIC New Company"
    assert delete_device(device["id"]) is True
    with pytest.raises(DeviceConfigError):
        delete_device(device["id"])


def test_company_is_required_for_service_create_and_explicit_update():
    with pytest.raises(DeviceConfigError, match="所属公司不能为空"):
        add_device("SYNTHETIC Device", "   ")

    device = add_device("SYNTHETIC Device", "SYNTHETIC Company")
    with pytest.raises(DeviceConfigError, match="所属公司不能为空"):
        update_device(device["id"], company="\t")
    assert list_devices()[-1]["company"] == "SYNTHETIC Company"


def test_company_lookup_ignores_case_and_whitespace_but_rejects_ambiguity():
    add_device("SYNTHETIC Device A", "SYNTHETIC Company A")
    assert company_for_device_name(" syntheticdevicea ") == "SYNTHETIC Company A"
    assert company_for_device_name("SYNTHETIC MISSING") == ""

    add_device("synthetic device a", "SYNTHETIC Company B")
    assert company_for_device_name("SYNTHETIC DEVICE A") == ""


def test_update_nonexistent_raises():
    with pytest.raises(DeviceConfigError, match="不存在"):
        update_device("device-SYNTHETIC-missing", name="SYNTHETIC X")


def test_delete_nonexistent_raises():
    with pytest.raises(DeviceConfigError, match="不存在"):
        delete_device("device-SYNTHETIC-missing")
