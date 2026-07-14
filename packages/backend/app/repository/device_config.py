"""
Layer 20: BE_Repository — 硬件设备配置存取

存储位置: packages/backend/app/data/hardware_devices.json
"""

import json
import os
import uuid
from typing import Optional


CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CONFIG_FILE = os.path.join(CONFIG_DIR, "hardware_devices.json")

# 默认设备
DEFAULT_DEVICES = [
    {
        "id": "default-fl901",
        "name": "FL-901 手机取证塔",
        "model": "美亚FL-901",
        "description": "美亚柏科手机取证塔，支持主流手机数据提取",
    },
]


def _ensure_config() -> None:
    """确保配置文件存在，不存在则创建默认"""
    if not os.path.exists(CONFIG_FILE):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_DEVICES, f, ensure_ascii=False, indent=2)


def _read_config() -> list[dict]:
    """读取配置"""
    _ensure_config()
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_config(devices: list[dict]) -> None:
    """写入配置"""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(devices, f, ensure_ascii=False, indent=2)


def list_devices() -> list[dict]:
    """获取所有硬件设备"""
    return _read_config()


def add_device(name: str, model: str, description: str = "") -> dict:
    """添加设备"""
    devices = _read_config()
    device = {
        "id": str(uuid.uuid4())[:8],
        "name": name,
        "model": model,
        "description": description,
    }
    devices.append(device)
    _write_config(devices)
    return device


def update_device(device_id: str, name: str = "", model: str = "", description: str = "") -> Optional[dict]:
    """更新设备，返回更新后的设备或 None"""
    devices = _read_config()
    for d in devices:
        if d["id"] == device_id:
            if name:
                d["name"] = name
            if model:
                d["model"] = model
            if description is not None:
                d["description"] = description
            _write_config(devices)
            return d
    return None


def delete_device(device_id: str) -> bool:
    """删除设备，返回是否成功"""
    devices = _read_config()
    new_devices = [d for d in devices if d["id"] != device_id]
    if len(new_devices) == len(devices):
        return False
    _write_config(new_devices)
    return True
