"""
Layer 20: BE_Repository — 美亚手机大师 HTML 报告解析器

解析美亚 FL-901V5 生成的 HTML 报告中的 JSON 数据文件。
支持标准文件夹格式：[案件名称]_[时间戳]_html/

解析目标文件：
- data/data_case_info.json    — 案件信息
- data/data_device_lists.json — 设备列表
- data/data_report_info.json  — 取证工具版本
- data/data_navigation.json   — 数据分类树
- data/[检材编号]/Base/       — 设备基本信息（型号/IMEI）
"""

import json
import os
import re
from typing import Any
from .device_field_parser import extract_device_fields, try_parse_json
from .navigation_parser import parse_navigation
from .json_loader import load_js_json
class ReportParseError(Exception): pass
def _load_js_json(filepath: str) -> Any:
    """
    加载美亚 JS 变量赋值格式的 JSON 文件。
    格式: ; static.mypico.json.xxx = <JSON>
    """
    if not os.path.exists(filepath):
        raise ReportParseError(f"文件不存在: {filepath}")

    with open(filepath, "r", encoding="utf-8-sig") as f:
        content = f.read()
    # 去掉 JS 变量赋值前缀
    json_str = re.sub(
        r'^;\s*static\.mypico\.(?:json\.)?\w+\s*=\s*',
        "",
        content.strip(),
    )
    if not json_str:
        raise ReportParseError(f"无法解析 JSON: {filepath}")
    return json.loads(json_str)
def _find_value(contents: list[dict], tp_field: str, value_field: str = "ct") -> str:
    """从 data_case_info 的 contents 列表中按 tp 字段查找值"""
    for item in contents:
        if item.get("tp") == tp_field:
            return item.get(value_field, "")
    return ""
def parse_case_info(data_dir: str) -> dict[str, str]:
    """解析 data_case_info.json，返回案件信息字典"""
    filepath = os.path.join(data_dir, "data_case_info.json")
    data = load_js_json(filepath)
    contents = data.get("contents", [])
    return {
        "case_name": _find_value(contents, "案件名称"),
        "case_number": _find_value(contents, "案件编号"),
        "collector": _find_value(contents, "采集人"),
        "collect_unit": _find_value(contents, "采集单位"),
        "submit_person": _find_value(contents, "送检人"),
        "submit_unit": _find_value(contents, "送检单位"),
        "case_type": _find_value(contents, "案件类型"),
        "report_time": _find_value(contents, "报告时间"),
        "create_time": _find_value(contents, "创建时间"),
    }
def parse_device_lists(data_dir: str) -> list[dict[str, str]]:
    """解析 data_device_lists.json，返回设备列表"""
    filepath = os.path.join(data_dir, "data_device_lists.json")
    data = load_js_json(filepath)
    contents = data.get("contents", []) if isinstance(data, dict) else data
    devices = []
    for index, item in enumerate(contents or []):
        if not isinstance(item, dict):
            continue
        time_range = item.get("c3", "") or item.get("time_range", "")
        parts = time_range.split(" ~ ") if " ~ " in time_range else (time_range, time_range)
        evidence_number = (
            item.get("c2", "")
            or item.get("evidence_number", "")
            or item.get("evidence_name", "")
            or _find_evidence_directory(data_dir, index)
        )
        devices.append({
            "evidence_number": evidence_number,
            "start_time": parts[0].strip(),
            "end_time": parts[1].strip() if len(parts) > 1 else parts[0].strip(),
            "time_range": time_range,
        })
    if not devices:
        for evidence_number in _evidence_directories(data_dir):
            devices.append({
                "evidence_number": evidence_number,
                "start_time": "",
                "end_time": "",
                "time_range": "",
            })
    return devices
def _evidence_directories(data_dir: str) -> list[str]:
    if not os.path.isdir(data_dir):
        return []
    return sorted(
        name for name in os.listdir(data_dir)
        if os.path.isdir(os.path.join(data_dir, name))
        and re.match(r"(?i)^JC[A-Z0-9_-]+$", name)
    )
def _find_evidence_directory(data_dir: str, index: int) -> str:
    directories = _evidence_directories(data_dir)
    return directories[index] if index < len(directories) else ""
def parse_report_info(data_dir: str) -> dict[str, str]:
    """解析 data_report_info.json，返回取证工具版本信息"""
    filepath = os.path.join(data_dir, "data_report_info.json")
    data = load_js_json(filepath)
    contents = data.get("contents", [])
    versions = {}
    for item in contents:
        value = item.get("value", "")
        if "产品版本" in value:
            versions["product_version"] = value.split("：")[-1].strip()
        elif "平台版本" in value:
            versions["platform_version"] = value.split("：")[-1].strip()
        elif "国内应用版本" in value:
            versions["app_version"] = value.split("：")[-1].strip()

    return versions
def parse_navigation(data_dir: str) -> dict[str, Any]:
    """
    解析 data_navigation.json 树结构。
    返回:
    - categories: 数据分类名称列表（如 "即时通讯", "手机信息"）
    - total_items: 总提取数据量
    """
    filepath = os.path.join(data_dir, "data_navigation.json")
    raw = None
    with open(filepath, "rb") as f:
        content = f.read()

    # 尝试解析整个 JSON（可能因编码问题失败），降级为逐条提取
    json_str_match = re.search(rb'=\s*(\[.*)', content, re.DOTALL)
    if not json_str_match:
        return {"categories": [], "total_items": 0}

    try:
        data = json.loads(json_str_match.group(1))
    except json.JSONDecodeError:
        # 降级：从 raw text 提取 name 字段
        return _parse_navigation_fallback(content)

    categories = []
    total_items = 0

    def traverse(nodes):
        nonlocal total_items
        for node in nodes:
            name = node.get("name", "")
            total_node = node.get("dataTotal", 0)
            if total_node and name:
                total_items += total_node
            pid = node.get("pid", "")
            # 根节点下第一层为分类
            if pid and pid != "report_info" and pid != "device_lists":
                # 检查是否已有数据配置（即实际数据节点）
                if node.get("dataConfig", {}).get("varName") and name:
                    if name not in categories:
                        categories.append(name)
            traverse(node.get("children", []))
    traverse(data if isinstance(data, list) else [])
    return {"categories": categories, "total_items": total_items}
def _parse_navigation_fallback(raw: bytes) -> dict[str, Any]:
    """navigation JSON 解析失败时的降级提取方案"""
    names = re.findall(rb'"name":"([^"]{1,60})"', raw)
    total = 0
    categories = set()
    totals = re.findall(rb'"dataTotal":(\d+)', raw)

    for name_bytes in names:
        try:
            name = name_bytes.decode("utf-8")
            # 过滤明显的电话号码、微信号等个人数据
            if (not name.replace(" ", "").isdigit()
                    and "wxid_" not in name
                    and "@chatroom" not in name
                    and len(name) > 1):
                categories.add(name)
        except UnicodeDecodeError:
            pass
    total = sum(int(t) for t in totals) if totals else 0
    return {"categories": list(categories)[:20], "total_items": total}
def parse_device_base(data_dir: str, evidence_number: str) -> dict[str, str]:
    """
    解析 data/[编号]/Base/ 下的设备基本信息。
    返回设备型号、IMEI、序列号等。
    """
    base_dir = os.path.join(data_dir, evidence_number, "Base")
    if not os.path.exists(base_dir):
        return {"device_name": "", "model": "", "imei1": "", "imei2": "", "serial_number": ""}
    result = {"device_name": "", "model": "", "imei1": "", "imei2": "", "serial_number": ""}
    for fname in os.listdir(base_dir):
        if not fname.endswith(".json"):
            continue
        filepath = os.path.join(base_dir, fname)
        try:
            with open(filepath, "rb") as f:
                raw = f.read()
            # 从 JSON 中提取手机基本信息
            text = raw.decode("utf-8", errors="replace")

            # 提取型号
            model_match = re.search(r'iPhone[\s\d\w]*Pro[\s\d\w]*|HUAWEI[\s\w\d\-]+|'
                                   r'小米[\s\w\d]+|OPPO[\s\w\d]+|vivo[\s\w\d]+|'
                                   r'Samsung[\s\w\d]+|OnePlus[\s\w\d]+',
                                   text)
            if model_match and not result["model"]:
                result["model"] = model_match.group(0)

            # 提取 IMEI
            imei_matches = re.findall(r'IMEI[:\s]*(\d{15})', text, re.IGNORECASE)
            if len(imei_matches) >= 1 and not result["imei1"]:
                result["imei1"] = imei_matches[0]
            if len(imei_matches) >= 2 and not result["imei2"]:
                result["imei2"] = imei_matches[1]
            # 提取序列号
            sn_match = re.search(r'(?:序列号|Serial)[:\s]*([A-Za-z0-9]+)', text)
            if sn_match and not result["serial_number"]:
                result["serial_number"] = sn_match.group(1)

            payload = try_parse_json(text)
            extracted = extract_device_fields(payload, text)
            for key, value in extracted.items():
                if value and not result[key]:
                    result[key] = value
            if not result["device_name"]:
                result["device_name"] = result["model"]
            if not result["model"]:
                result["model"] = result["device_name"]
            imei_matches = re.findall(r"(?<!\d)\d{15}(?!\d)", text)
            if not result["imei1"] and imei_matches:
                result["imei1"] = imei_matches[0]
            if not result["imei2"] and len(imei_matches) > 1:
                result["imei2"] = imei_matches[1]
            if not result["serial_number"]:
                serial_match = re.search(
                    r"(?:序列号|serial[_ ]?number|serial|sn)\D{0,20}([A-Za-z0-9]{6,})",
                    text,
                    re.IGNORECASE,
                )
                if serial_match:
                    result["serial_number"] = serial_match.group(1)
        except Exception:
            continue
    return result
