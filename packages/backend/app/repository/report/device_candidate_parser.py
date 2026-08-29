"""报告中新格式设备信息表的候选提取和保守选择。"""

from typing import Any

from .device_field_parser import extract_device_fields, normalise_imei

_EMPTY_FIELDS = {"device_type": "", "device_name": "", "brand": "", "model": "", "imei1": "", "imei2": "", "serial_number": ""}
_IDENTITY_FIELDS = {"device_name", "brand", "model", "serial_number"}


def select_best_device_candidate(payloads: list[Any], *, allow_tt_ct: bool) -> dict[str, str]:
    candidates = []
    for payload in payloads:
        for structure, table in _iter_logical_tables(payload, allow_tt_ct=allow_tt_ct):
            fields = extract_device_fields(
                table, "", allow_tt_ct=allow_tt_ct,
                allow_text_fallback=False, fill_missing_aliases=False,
            )
            fields["imei1"] = normalise_imei(fields["imei1"])
            fields["imei2"] = normalise_imei(fields["imei2"])
            if not _is_candidate(fields):
                continue
            candidates.append((
                _candidate_score(fields, structure),
                _field_count(fields),
                fields,
            ))

    if not candidates:
        return dict(_EMPTY_FIELDS)
    best_score = max((score, count) for score, count, _ in candidates)
    winners = [fields for score, count, fields in candidates if (score, count) == best_score]
    first = winners[0]
    if all(fields == first for fields in winners[1:]):
        return first
    # 同分且字段冲突时保守留空，避免路径顺序制造虚构设备。
    return dict(_EMPTY_FIELDS)


def _is_candidate(fields: dict[str, str]) -> bool:
    return _field_count(fields) >= 3 and any(fields[key] for key in _IDENTITY_FIELDS)


def _field_count(fields: dict[str, str]) -> int:
    return sum(bool(fields[key]) for key in _EMPTY_FIELDS)


def _candidate_score(fields: dict[str, str], structure: str) -> int:
    score = sum({
        "serial_number": 4, "model": 3, "device_name": 3, "brand": 3,
        "device_type": 1,
        "imei1": 3, "imei2": 3,
    }[key] for key in _EMPTY_FIELDS if fields[key])
    return score + (1 if structure == "mapping" else 2)


def _iter_logical_tables(value: Any, *, allow_tt_ct: bool):
    if isinstance(value, dict):
        direct = {
            key: child for key, child in value.items()
            if _is_device_label(key) and _is_scalar(child)
        }
        if direct:
            yield "mapping", direct
        for child in value.values():
            yield from _iter_logical_tables(child, allow_tt_ct=allow_tt_ct)
        return
    if isinstance(value, list):
        rows = [row for row in value if isinstance(row, dict) and _is_table_row(row, allow_tt_ct)]
        if rows:
            structure = "ttct" if any("tt" in row and "ct" in row for row in rows) else "c1c2"
            yield structure, rows
            return
        for child in value:
            yield from _iter_logical_tables(child, allow_tt_ct=allow_tt_ct)


def _is_table_row(row: dict[str, Any], allow_tt_ct: bool) -> bool:
    if _is_scalar(row.get("c1")) and _is_scalar(row.get("c2")):
        return True
    return allow_tt_ct and _is_scalar(row.get("tt")) and _is_scalar(row.get("ct"))


def _is_device_label(label: Any) -> bool:
    key = "".join(str(label).split()).lower()
    return key in {
        "设备类型", "检材类型", "终端类型", "设备名称", "检材名称", "设备型号", "产品型号", "手机型号",
        "机型", "设备机型", "手机机型", "硬件型号", "硬件机型", "型号名称", "型号",
        "model", "devicemodel", "productmodel", "phonemodel", "modelname", "hardwaremodel",
        "手机品牌", "设备品牌", "品牌", "品牌名称", "制造商", "厂商", "brand",
        "phonebrand", "devicebrand", "manufacturer",
        "imei", "imei1", "imei2", "序列号", "serial", "serialnumber", "sn",
    }


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))
