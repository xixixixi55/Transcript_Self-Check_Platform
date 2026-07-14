"""T008: 设备配置存取测试"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'packages', 'backend'))

from app.repository.device_config import list_devices, add_device, delete_device


def test_list_default_devices():
    devices = list_devices()
    assert len(devices) >= 1
    assert any("FL-901" in d.get("name", "") for d in devices)


def test_add_device():
    device = add_device("Test Device", "TD-100", "Test description")
    assert device["name"] == "Test Device"
    assert device["model"] == "TD-100"
    assert "id" in device
    delete_device(device["id"])


def test_delete_device():
    device = add_device("Temp Device", "TM-1")
    assert delete_device(device["id"]) is True
    assert delete_device(device["id"]) is False  # already deleted
