"""Layer 20: BE_Repository — 硬件设备配置存取。

存储位置: packages/backend/app/data/hardware_devices.json
"""
import json
import os
import uuid
from typing import Optional

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
CONFIG_FILE = os.path.join(CONFIG_DIR, "hardware_devices.json")

_DEFAULT_DEVICES = [
    {
        "id": "default-fl901",
        "name": "美亚FL-901 手机取证塔",
        "company": "美亚柏科",
    },
]


def _ensure_config() -> None:
    if not os.path.exists(CONFIG_FILE):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(_DEFAULT_DEVICES, f, ensure_ascii=False, indent=2)


def _read_config() -> list[dict]:
    _ensure_config()
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return [_normalise_device(item) for item in json.load(f)]


def _normalise_device(device: dict) -> dict:
    return {
        "id": str(device.get("id") or "").strip(),
        "name": str(device.get("name") or "").strip(),
        "company": str(device.get("company") or "").strip(),
    }


def _write_config(devices: list[dict]) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(devices, f, ensure_ascii=False, indent=2)


def list_all() -> list[dict]:
    return _read_config()


def insert(name: str, company: str) -> dict:
    devices = _read_config()
    device = {
        "id": str(uuid.uuid4())[:8], "name": name, "company": company,
    }
    devices.append(device)
    _write_config(devices)
    return device


def update(
    device_id: str, name: str = "",
    company: Optional[str] = None,
) -> Optional[dict]:
    devices = _read_config()
    for d in devices:
        if d["id"] == device_id:
            if name: d["name"] = name
            if company is not None: d["company"] = company
            _write_config(devices)
            return d
    return None


def delete(device_id: str) -> bool:
    devices = _read_config()
    new_devices = [d for d in devices if d["id"] != device_id]
    if len(new_devices) == len(devices): return False
    _write_config(new_devices)
    return True
