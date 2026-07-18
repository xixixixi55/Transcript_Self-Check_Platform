"""
Layer 20: BE_Repository — 美亚手机大师 HTML 报告解析器

解析美亚 FL-901V5 生成的 HTML 报告中的 JSON 数据文件。
支持标准文件夹格式：[案件名称]_[时间戳]_html/

> 文件行数超过 250 行上限：本文件是报告解析的入口，包含 6 个 JSON 文件解析函数
  （case_info / device_lists / report_info / navigation / device_base / device_field）
  及目录扫描、时间格式化等辅助函数。按数据源拆分会导致多层 import 循环。
  已归档至 FILE_SIZE_EXCEPTIONS。

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
import unicodedata
from datetime import datetime
from typing import Any
from .device_candidate_parser import select_best_device_candidate
from .device_field_parser import extract_device_fields, try_parse_json
from .navigation_parser import parse_navigation
from .json_loader import load_js_json
from .report_format_adapter import (
    ReportFormat, extract_main_software_version, require_supported_report_format,
)
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
    report_format = require_supported_report_format(data_dir)
    for item in contents or []:
        if not isinstance(item, dict):
            continue
        tb2_fields = {}
        if report_format == ReportFormat.NEW and isinstance(item.get("tb2"), list):
            tb2_fields = extract_device_fields(
                item["tb2"], "", allow_tt_ct=True,
                allow_text_fallback=False, fill_missing_aliases=False,
            )
        time_range = item.get("c3", "") or item.get("time_range", "")
        parts = time_range.split(" ~ ") if " ~ " in time_range else (time_range, time_range)
        evidence_number = str(
            item.get("c2", "")
            or item.get("evidence_number", "")
            or item.get("evidence_name", "")
        ).strip()
        # Legacy c1 is a device label; new c1 is only a row sequence.
        if report_format == ReportFormat.LEGACY:
            device_name = item.get("c1", "") or item.get("device_name", "") or item.get("device_type", "")
        else:
            device_name = item.get("device_name", "") or item.get("device_type", "")
        devices.append({
            "evidence_number": evidence_number,
            "device_name": device_name,
            "device_type": str(tb2_fields.get("device_type") or item.get("device_type", "")).strip(),
            "imei1": tb2_fields.get("imei1", ""),
            "imei2": tb2_fields.get("imei2", ""),
            "start_time": parts[0].strip(),
            "end_time": parts[1].strip() if len(parts) > 1 else parts[0].strip(),
            "time_range": time_range,
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
def _normalise_directory_name(value: str) -> str:
    return unicodedata.normalize("NFKC", str(value)).strip().casefold()


def _resolve_evidence_directory(data_dir: str, evidence_number: str) -> str:
    """Resolve only the explicitly named specimen directory.

    A normalized match is allowed for harmless whitespace/full-width/case
    differences, but no positional or arbitrary Base-directory fallback is
    permitted.
    """
    if not evidence_number or not os.path.isdir(data_dir):
        return ""
    direct = os.path.join(data_dir, evidence_number)
    if os.path.isdir(direct):
        return direct
    target = _normalise_directory_name(evidence_number)
    matches = [
        name for name in os.listdir(data_dir)
        if os.path.isdir(os.path.join(data_dir, name))
        and _normalise_directory_name(name) == target
    ]
    return os.path.join(data_dir, matches[0]) if len(matches) == 1 else ""


def find_base_directories(data_dir: str) -> list[str]:
    """扫描 data_dir 下所有包含 Base/ 子目录的目录（不限于 JC 前缀）"""
    if not os.path.isdir(data_dir):
        return []
    result = []
    for name in os.listdir(data_dir):
        full = os.path.join(data_dir, name)
        if os.path.isdir(full) and os.path.isdir(os.path.join(full, "Base")):
            result.append(name)
    return sorted(result)


def format_time_chinese(iso_str: str) -> str:
    """将 ISO 时间字符串转换为中文格式。如 '2026-06-30' → '2026年6月30日'"""
    if not iso_str:
        return ""
    import re as _re
    # 尝试匹配 YYYY-MM-DD 或 YYYY/MM/DD 等常见格式
    m = _re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", iso_str.strip())
    if m:
        return f"{m.group(1)}年{int(m.group(2))}月{int(m.group(3))}日"
    # 若已是中文格式则直接返回
    if "年" in iso_str:
        return iso_str
    return iso_str


def format_time_range_chinese(time_range: str) -> str:
    """将原始时间范围转换为中文格式。
    '2026-07-07 16:00:22 ~ 2026-07-07 16:05:39' → '2026年7月7日16点00分至2026年7月7日16点05分'
    """
    if not time_range:
        return ""
    import re as _re
    parts = time_range.split(" ~ ")
    if len(parts) != 2:
        return time_range
    formatted = []
    for part in parts:
        m = _re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})\s+(\d{1,2}):(\d{2})(?::(\d{2}))?", part.strip())
        if m:
            y, mo, d, h, mi = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)), m.group(5)
            formatted.append(f"{y}年{mo}月{d}日{h}点{mi}分")
        else:
            formatted.append(part)
    return "至".join(formatted)


def format_inspection_time_range(start_time: str, end_time: str) -> str:
    """按案件创建/报告时间生成分钟精度的检查起止时间。"""
    start_dt = _parse_datetime(start_time)
    end_dt = _parse_datetime(end_time)
    if not start_dt or not end_dt or start_dt > end_dt:
        return ""
    return f"{_format_datetime_minute(start_dt)}至{_format_datetime_minute(end_dt)}"


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    normalized = str(value).strip()
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M"):
        try:
            return datetime.strptime(normalized, pattern)
        except ValueError:
            continue
    return None


def _format_datetime_minute(value: datetime) -> str:
    return f"{value.year}年{value.month}月{value.day}日{value.hour}点{value.minute:02d}分"


def parse_report_info(data_dir: str) -> dict[str, str]:
    """解析 data_report_info.json，返回取证工具版本信息"""
    filepath = os.path.join(data_dir, "data_report_info.json")
    data = load_js_json(filepath)
    contents = data.get("contents", [])
    versions = {}
    for item in contents:
        value = str(item.get("value", ""))
        if "产品版本" in value:
            versions["product_version"] = value.split("：")[-1].strip()
        elif "平台版本" in value:
            versions["platform_version"] = value.split("：")[-1].strip()
        elif "国内应用版本" in value:
            versions["app_version"] = value.split("：")[-1].strip()

    main_version = extract_main_software_version(contents)
    if main_version:
        versions["product_version"] = main_version

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
    解析 data/[编号]/ 下的设备基本信息。
    优先扫描 Base/ 目录，其次 Phone/ 目录。
    返回设备型号、IMEI、序列号等。
    """
    resolved_dir = _resolve_evidence_directory(data_dir, evidence_number)
    if not resolved_dir:
        return {"device_type": "", "device_name": "", "model": "", "imei1": "", "imei2": "", "serial_number": ""}

    report_format = require_supported_report_format(data_dir)
    json_files = []
    for sub in sorted(os.listdir(resolved_dir)):
        sub_path = os.path.join(resolved_dir, sub)
        if os.path.isdir(sub_path):
            for fname in sorted(os.listdir(sub_path)):
                if fname.lower().endswith(".json"):
                    json_files.append(os.path.join(sub_path, fname))

    if report_format == ReportFormat.NEW:
        payloads = []
        for filepath in sorted(json_files):
            try:
                with open(filepath, "rb") as f:
                    payloads.append(try_parse_json(f.read().decode("utf-8", errors="replace")))
            except OSError:
                continue
        return select_best_device_candidate(payloads, allow_tt_ct=True)

    # Keep the legacy explicit labels and text fallback. The fallback is
    # bounded by known labels and never scans arbitrary 15-digit numbers.
    result = {"device_type": "", "device_name": "", "model": "", "imei1": "", "imei2": "", "serial_number": ""}
    for filepath in sorted(json_files):
        try:
            with open(filepath, "rb") as f:
                raw = f.read()
            payload = try_parse_json(raw.decode("utf-8", errors="replace"))
            extracted = extract_device_fields(payload, raw.decode("utf-8", errors="replace"), allow_text_fallback=True)
            for key, value in extracted.items():
                if value and not result[key]:
                    result[key] = value
        except (OSError, UnicodeError):
            continue
    if not result["device_name"]:
        result["device_name"] = result["model"]
    if not result["model"]:
        result["model"] = result["device_name"]
    return result
