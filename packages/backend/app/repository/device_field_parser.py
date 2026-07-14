"""Layer 20: Base 目录设备字段兼容解析。"""

import json
import re
from typing import Any


def try_parse_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"=\s*(\{.*\}|\[.*\])\s*;?\s*$", text, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return {}


def extract_device_fields(payload: Any, text: str) -> dict[str, str]:
    result = {"device_name": "", "model": "", "imei1": "", "imei2": "", "serial_number": ""}

    def assign(label: str, value: Any):
        if value is None or isinstance(value, (dict, list)):
            return
        value_text = str(value).strip()
        if not value_text:
            return
        key = _normalise_key(label)
        if key in {"设备名称", "手机名称", "devicename", "phonename", "productname"}:
            result["device_name"] = result["device_name"] or value_text
        elif key in {"型号", "model", "devicemodel", "phonemodel"}:
            result["model"] = result["model"] or value_text
        elif key in {"imei1", "imei-1"}:
            result["imei1"] = result["imei1"] or value_text
        elif key in {"imei2", "imei-2"}:
            result["imei2"] = result["imei2"] or value_text
        elif key in {"序列号", "serial", "serialnumber", "sn"}:
            result["serial_number"] = result["serial_number"] or value_text

    for key, value in _iter_key_values(payload):
        assign(key, value)
    for label, content in _iter_label_values(payload):
        assign(label, content)

    for field, aliases in {
        "imei1": r"IMEI\s*1|IMEI1",
        "imei2": r"IMEI\s*2|IMEI2",
        "serial_number": r"序列号|serial[_ ]?number|serial|sn",
        "device_name": r"设备名称|手机名称|device[_ ]?name|phone[_ ]?name",
        "model": r"型号|model",
    }.items():
        match = re.search(
            rf"(?:{aliases})\D{{0,20}}([A-Za-z0-9][A-Za-z0-9 ._-]{{2,60}})",
            text,
            re.IGNORECASE,
        )
        if match and not result[field]:
            result[field] = match.group(1).strip()

    if not result["device_name"]:
        result["device_name"] = result["model"]
    if not result["model"]:
        result["model"] = result["device_name"]
    return result


def _iter_key_values(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key), child
            yield from _iter_key_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_key_values(child)


def _iter_label_values(value: Any):
    if isinstance(value, dict):
        label = value.get("name") or value.get("key") or value.get("label") or value.get("title")
        content = value.get("value") or value.get("content") or value.get("text") or value.get("ct")
        if label and content is not None:
            yield str(label), content
        for child in value.values():
            yield from _iter_label_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_label_values(child)


def _normalise_key(value: str) -> str:
    return re.sub(r"[\s_\-:：]", "", value).lower()
