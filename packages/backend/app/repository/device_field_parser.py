"""Layer 20: Base 目录设备字段兼容解析。"""

import json
import re
from typing import Any

_GENERIC_DEVICE_LABELS = frozenset({
    "手机", "智能手机", "移动电话", "phone", "smartphone", "mobile phone",
    "mobile",
})


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


def extract_device_fields(
    payload: Any,
    text: str,
    *,
    allow_tt_ct: bool = False,
    allow_text_fallback: bool = True,
    fill_missing_aliases: bool = True,
) -> dict[str, str]:
    """提取已知设备字段。

    ``tt/ct`` 只有在调用方已经确认当前对象是键值表时才启用；默认保持
    旧格式的 ``信息/内容``、``c1/c2`` 和明确字段名行为。
    """
    result = {"device_type": "", "device_name": "", "brand": "", "model": "", "imei1": "", "imei2": "", "serial_number": ""}

    def assign(label: str, value: Any):
        if value is None or isinstance(value, (dict, list)):
            return
        value_text = str(value).strip()
        if not value_text:
            return
        key = _normalise_key(label)
        if key in {"device_type", "devicetype", "materialtype", "设备类型", "检材类型"}:
            result["device_type"] = result["device_type"] or value_text
        elif key in {"设备名称", "手机名称", "devicename", "phonename", "productname"}:
            result["device_name"] = result["device_name"] or value_text
        elif key in {
            "手机品牌", "设备品牌", "品牌", "品牌名称", "制造商", "厂商",
            "制造商名称", "phonebrand", "devicebrand", "brand", "manufacturer",
        }:
            result["brand"] = result["brand"] or value_text
        elif key in {
            "型号", "设备型号", "产品型号", "手机型号", "机型", "设备机型",
            "手机机型", "硬件型号", "硬件机型", "型号名称", "model",
            "devicemodel", "productmodel", "phonemodel", "modelname",
            "hardwaremodel",
        }:
            result["model"] = result["model"] or value_text
        elif key in {"imei1", "imei-1"}:
            result["imei1"] = result["imei1"] or normalise_imei(value_text)
        elif key in {"imei2", "imei-2"}:
            result["imei2"] = result["imei2"] or normalise_imei(value_text)
        elif key in {"序列号", "serial", "serialnumber", "sn"}:
            result["serial_number"] = result["serial_number"] or value_text

    for key, value in _iter_key_values(payload):
        assign(key, value)
    for label, content in _iter_label_values(payload, allow_tt_ct=allow_tt_ct):
        assign(label, content)

    if allow_text_fallback:
        for field, aliases in {
            "imei1": r"IMEI\s*1|IMEI1",
            "imei2": r"IMEI\s*2|IMEI2",
            "serial_number": r"序列号|serial[_ ]?number|serial|sn",
            "device_name": r"设备名称|手机名称|device[_ ]?name|phone[_ ]?name",
            "brand": r"手机品牌|设备品牌|品牌(?:名称)?|制造商|厂商|manufacturer|phone[_ ]?brand|device[_ ]?brand",
            "model": r"设备型号|产品型号|手机型号|设备机型|手机机型|硬件型号|机型|型号|model",
            "device_type": r"设备类型|检材类型|device[_ ]?type|material[_ ]?type",
        }.items():
            match = re.search(
                rf"(?:{aliases})\D{{0,20}}([A-Za-z0-9][A-Za-z0-9 ._-]{{2,60}})",
                text,
                re.IGNORECASE,
            )
            if match and not result[field]:
                result[field] = match.group(1).strip()

    if fill_missing_aliases:
        if not result["device_name"] and result["model"]:
            result["device_name"] = result["model"]
        if not result["model"] and result["device_name"] and not is_generic_device_label(result["device_name"]):
            result["model"] = result["device_name"]
    return result


def extract_strong_device_fields(
    payload: Any,
    text: str = "",
    *,
    allow_tt_ct: bool = False,
) -> dict[str, str]:
    """只从结构明确且包含多个强字段的设备信息表提取字段。"""
    if not _contains_key_value_table(payload, allow_tt_ct=allow_tt_ct):
        return _empty_fields()
    fields = extract_device_fields(
        payload,
        text,
        allow_tt_ct=allow_tt_ct,
        allow_text_fallback=False,
        fill_missing_aliases=False,
    )
    strong_values = [fields[key] for key in fields if fields[key]]
    return fields if len(strong_values) >= 3 else _empty_fields()


def _iter_key_values(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key), child
            yield from _iter_key_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_key_values(child)


def _iter_label_values(value: Any, *, allow_tt_ct: bool = False):
    if isinstance(value, dict):
        label = (value.get("name") or value.get("key") or value.get("label") or value.get("title")
                 or value.get("信息") or value.get("c1")
                 or (value.get("tt") if allow_tt_ct else None))
        content = (value.get("value") or value.get("content") or value.get("text") or value.get("ct")
                   or value.get("内容") or value.get("c2")
                   or (value.get("ct") if allow_tt_ct else None))
        if label and content is not None:
            yield str(label), content
        for child in value.values():
            yield from _iter_label_values(child, allow_tt_ct=allow_tt_ct)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_label_values(child, allow_tt_ct=allow_tt_ct)


def _contains_key_value_table(value: Any, *, allow_tt_ct: bool) -> bool:
    if isinstance(value, dict):
        keys = {_normalise_key(str(key)) for key in value}
        if {"c1", "c2"}.issubset(keys):
            return True
        if allow_tt_ct and {"tt", "ct"}.issubset(keys):
            return True
        return any(_contains_key_value_table(child, allow_tt_ct=allow_tt_ct) for child in value.values())
    if isinstance(value, list):
        return any(_contains_key_value_table(child, allow_tt_ct=allow_tt_ct) for child in value)
    return False


def _empty_fields() -> dict[str, str]:
    return {"device_type": "", "device_name": "", "brand": "", "model": "", "imei1": "", "imei2": "", "serial_number": ""}


def normalise_imei(value: Any) -> str:
    """清理并校验 IMEI；非法占位值按空值处理。"""
    if value is None or isinstance(value, (dict, list, tuple, bool)):
        return ""
    compact = re.sub(r"[\s\-－—·]", "", str(value)).strip()
    if compact.lower() in {"", "unknown", "未知", "无", "n/a", "na", "null", "none"}:
        return ""
    return compact if re.fullmatch(r"\d{15}", compact) else ""


def _normalise_key(value: str) -> str:
    return re.sub(r"[\s_\-:：/／]", "", value).lower()


def is_generic_device_label(value: Any) -> bool:
    normalized = " ".join(str(value or "").split()).casefold()
    return normalized in _GENERIC_DEVICE_LABELS
