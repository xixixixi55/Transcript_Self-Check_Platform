"""Layer 20: BE_Repository — 用户数据根中的硬件设备配置存取。"""
import json
import os
import uuid
from pathlib import Path
from typing import Optional

from ..runtime.runtime_paths import get_runtime_paths

_RUNTIME_PATHS = get_runtime_paths()
CONFIG_DIR = str(_RUNTIME_PATHS.data_root)
CONFIG_FILE = os.path.join(CONFIG_DIR, "hardware_devices.json")
LEGACY_CONFIG_FILE = (
    str(Path(__file__).resolve().parent.parent / "data" / "hardware_devices.json")
    if _RUNTIME_PATHS.portable else None
)

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
        devices = _legacy_devices() if LEGACY_CONFIG_FILE else None
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(
                _DEFAULT_DEVICES if devices is None else devices,
                f, ensure_ascii=False, indent=2,
            )


def _legacy_devices() -> list[dict] | None:
    legacy_path = Path(LEGACY_CONFIG_FILE) if LEGACY_CONFIG_FILE else None
    config_path = Path(CONFIG_FILE)
    if not legacy_path or legacy_path == config_path or not legacy_path.is_file():
        return None
    try:
        with legacy_path.open("r", encoding="utf-8") as source:
            payload = json.load(source)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        return None
    return [_normalise_device(item) for item in payload]


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
