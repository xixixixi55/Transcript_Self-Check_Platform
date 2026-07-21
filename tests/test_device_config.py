"""T008: 设备配置存取测试 — 通过 Service 层访问"""
import os
import sys
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'packages', 'backend'))

from app.services.device_config_service import (
    list_devices, add_device, update_device, delete_device, DeviceConfigError,
)


def test_list_default_devices():
    devices = list_devices()
    assert len(devices) >= 1
    assert any("FL-901" in d.get("name", "") for d in devices)


def test_add_and_delete_device():
    device = add_device("Test Device", "TD-100", "Test description")
    assert device["name"] == "Test Device"
    assert device["model"] == "TD-100"
    assert "id" in device
    assert delete_device(device["id"]) is True
    with pytest.raises(DeviceConfigError):
        delete_device(device["id"])  # 已删除


def test_update_device():
    device = add_device("Update Test", "UT-1")
    updated = update_device(device["id"], name="Updated Name")
    assert updated["name"] == "Updated Name"
    delete_device(device["id"])


def test_add_duplicate_name_raises():
    device = add_device("Unique Device", "UD-1")
    try:
        with pytest.raises(DeviceConfigError, match="已存在"):
            add_device("Unique Device", "UD-2")
    finally:
        delete_device(device["id"])


def test_add_empty_name_raises():
    with pytest.raises(DeviceConfigError, match="不能为空"):
        add_device("", "M-1")


def test_update_nonexistent_raises():
    with pytest.raises(DeviceConfigError, match="不存在"):
        update_device("nonexistent-id", name="X")
