"""Report format detection and strict semantic compatibility helpers."""

import os
import re
from enum import Enum
from typing import Any

from .json_loader import load_js_json


_CONFIRMED_NEW_FIELDS = {
    "\u53d6\u8bc1\u65f6\u95f4\u6bb5",
    "\u68c0\u6750\u7f16\u53f7",
    "\u68c0\u6750\u7c7b\u578b",
    "imei1",
    "imei2",
    "\u8bbe\u5907\u578b\u53f7",
    "\u8bbe\u5907\u540d\u79f0",
    "\u5e8f\u5217\u53f7",
}
_VERSION_PATTERN = r"(?:[vV]\s*)?\d+(?:\.\d+){1,3}"
_VERSION_RE = re.compile(_VERSION_PATTERN)
_EXPLICIT_SOFTWARE_RE = re.compile(
    rf"(?:\u4e3b\u53d6\u8bc1\u8f6f\u4ef6|\u62a5\u544a\u751f\u6210\u8f6f\u4ef6)"
    rf"\s*[:\uff1a]\s*(?P<name>[\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9._+\- ]{{1,80}}?)"
    rf"\s+(?P<version>{_VERSION_PATTERN})(?=$|[\uFF0C,\uFF1B;\u3002)])",
    re.IGNORECASE,
)
_REPORT_USES_SOFTWARE_RE = re.compile(
    rf"\u62a5\u544a\u91c7\u7528\s*(?P<name>[\u4e00-\u9fffA-Za-z][\u4e00-\u9fffA-Za-z0-9._+\- ]{{1,80}}?)"
    rf"\s+(?P<version>{_VERSION_PATTERN})\s*\u751f\u6210",
    re.IGNORECASE,
)
_BRACKETED_REPORT_USES_SOFTWARE_RE = re.compile(
    rf"\u62a5\u544a\u91c7\u7528\s*[\u3010\[]\s*"
    rf"(?P<name>.+?)\s+(?P<version>{_VERSION_PATTERN})"
    rf"(?=\s+(?:\u5b50\u6a21\u5757|\u63d2\u4ef6|\u7ec4\u4ef6)|\s*[\u3011\]])",
    re.IGNORECASE,
)
_SOFTWARE_MARKERS = ("\u4e3b\u53d6\u8bc1\u8f6f\u4ef6", "\u62a5\u544a\u751f\u6210\u8f6f\u4ef6", "\u62a5\u544a\u91c7\u7528")
_BRACKETS = "()\uff08\uff09[]\u3010\u3011"
_HARDWARE_PARENTHESES_RE = re.compile(r"[\uff08(]([^\uff08\uff09()]*)[\uff09)]")
_HARDWARE_NAME_MARKERS = ("取证塔", "取证设备", "取证工作站", "采集设备", "硬件设备")


class ReportFormat(str, Enum):
    LEGACY = "legacy"
    NEW = "new"
    UNSUPPORTED = "unsupported"


class ReportFormatError(ValueError):
    """Core files exist but their structure is not a supported report format."""


def detect_report_format(data_dir: str) -> ReportFormat:
    """Detect a report from core structure, never from a report filename."""
    required = ["data_case_info.json", "data_device_lists.json", "data_report_info.json"]
    missing = [name for name in required if not os.path.exists(os.path.join(data_dir, name))]
    if missing:
        raise ReportFormatError(f"Missing report core files: {', '.join(missing)}")

    case_data = load_js_json(os.path.join(data_dir, "data_case_info.json"))
    device_data = load_js_json(os.path.join(data_dir, "data_device_lists.json"))
    report_data = load_js_json(os.path.join(data_dir, "data_report_info.json"))
    return detect_report_format_from_payloads(case_data, device_data, report_data)


def detect_report_format_from_payloads(
    case_data: Any, device_data: Any, report_data: Any,
) -> ReportFormat:
    """Detect format from one request's already-parsed core payloads."""
    if (
        not isinstance(case_data, dict)
        or not isinstance(case_data.get("contents"), list)
        or not isinstance(report_data, dict)
        or not isinstance(report_data.get("contents"), list)
    ):
        return ReportFormat.UNSUPPORTED
    rows = device_data.get("contents") if isinstance(device_data, dict) else None
    if not isinstance(rows, list):
        return ReportFormat.UNSUPPORTED

    has_new = any(_is_valid_new_row(row) for row in rows if isinstance(row, dict))
    has_legacy = any(_has_legacy_c3(row) for row in rows if isinstance(row, dict))
    if isinstance(device_data, dict) and isinstance(device_data.get("columns"), list):
        has_legacy = has_legacy or any(
            isinstance(column, dict)
            and (column.get("key") == "c3" or _normalise_key(column.get("title")) == "\u53d6\u8bc1\u65f6\u95f4\u6bb5")
            for column in device_data["columns"]
        )
    has_legacy = has_legacy or any(
        "\u4ea7\u54c1\u7248\u672c" in value for value in _report_values(report_data)
    )

    if has_new:
        return ReportFormat.NEW
    if has_legacy:
        return ReportFormat.LEGACY
    return ReportFormat.UNSUPPORTED


def require_supported_report_format(data_dir: str) -> ReportFormat:
    report_format = detect_report_format(data_dir)
    if report_format == ReportFormat.UNSUPPORTED:
        raise ReportFormatError(
            "Unsupported report core structure: data_device_lists must contain valid c3 or tb2 rows"
        )
    return report_format


def _is_valid_new_row(row: dict[str, Any]) -> bool:
    if not _has_text_scalar(row.get("c2")):
        return False
    tb2 = row.get("tb2")
    if not isinstance(tb2, list) or not tb2:
        return False
    return any(_is_valid_tt_ct_row(item) for item in tb2 if isinstance(item, dict))


def _is_valid_tt_ct_row(row: dict[str, Any]) -> bool:
    return (
        _has_text_scalar(row.get("tt"))
        and _has_text_scalar(row.get("ct"))
        and _normalise_key(row["tt"]) in _CONFIRMED_NEW_FIELDS
    )


def _has_legacy_c3(row: dict[str, Any]) -> bool:
    return _has_text_scalar(row.get("c3"))


def _has_text_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool)) and bool(str(value).strip())


def _report_values(value: Any) -> list[str]:
    if not isinstance(value, dict) or not isinstance(value.get("contents"), list):
        return []
    return [str(item.get("value", "")) for item in value["contents"] if isinstance(item, dict)]


def _normalise_key(value: Any) -> str:
    return "".join(str(value).split()).replace(":", "").replace("\uff1a", "").lower()


def extract_main_software_version(contents: Any) -> str:
    """Extract only a reliably bound main-software name/version pair."""
    if not isinstance(contents, list):
        return ""
    candidates: list[tuple[str, str]] = []
    saw_main_record = False
    for item in contents:
        if not isinstance(item, dict):
            continue
        value = str(item.get("value", "")).strip()
        if not value:
            continue
        if not any(marker in value for marker in _SOFTWARE_MARKERS):
            continue
        saw_main_record = True
        matches = _main_software_matches(value)
        if not matches:
            return ""
        for match in matches:
            fragment = match.group(0)
            if match.re is not _BRACKETED_REPORT_USES_SOFTWARE_RE and (
                any(bracket in fragment for bracket in _BRACKETS)
                or len(_VERSION_RE.findall(fragment)) != 1
            ):
                return ""
            name = normalize_main_software_name(match.group("name"))
            version = match.group("version").replace(" ", "")
            if not name or not version:
                return ""
            candidates.append((name, version))
    if not saw_main_record or not candidates or len(set(candidates)) != 1:
        return ""
    return candidates[0][1]


def extract_main_software_candidate(contents: Any) -> dict[str, Any]:
    """Return a report-bound software candidate without using runtime defaults."""
    if not isinstance(contents, list):
        return {"name": "", "version": "", "status": "unconfirmed", "candidates": []}

    candidates: list[tuple[str, str]] = []
    saw_marker = False
    invalid = False
    for item in contents:
        if not isinstance(item, dict):
            continue
        value = str(item.get("value", "")).strip()
        if not value or not any(marker in value for marker in _SOFTWARE_MARKERS):
            continue
        saw_marker = True
        matches = _main_software_matches(value)
        if not matches or any(
            match.re is not _BRACKETED_REPORT_USES_SOFTWARE_RE and
            bracket in match.group(0)
            for match in matches
            for bracket in _BRACKETS
        ):
            invalid = True
            continue
        for match in matches:
            fragment = match.group(0)
            if (match.re is not _BRACKETED_REPORT_USES_SOFTWARE_RE
                    and len(_VERSION_RE.findall(fragment)) != 1):
                invalid = True
                continue
            name = normalize_main_software_name(match.group("name"))
            version = match.group("version").replace(" ", "")
            if name and version:
                candidates.append((name, version))
            else:
                invalid = True

    unique = list(dict.fromkeys(candidates))
    status = "confirmed_by_report" if saw_marker and len(unique) == 1 and not invalid else "unconfirmed"
    name, version = unique[0] if status == "confirmed_by_report" else ("", "")
    return {
        "name": name,
        "version": version,
        "status": status,
        "candidates": [{"name": item[0], "version": item[1]} for item in unique],
    }


def _main_software_matches(value: str) -> list[re.Match[str]]:
    """Prefer the explicit bracketed main-product segment over submodules."""
    bracketed = list(_BRACKETED_REPORT_USES_SOFTWARE_RE.finditer(value))
    if bracketed:
        return bracketed
    matches = list(_EXPLICIT_SOFTWARE_RE.finditer(value))
    matches.extend(_REPORT_USES_SOFTWARE_RE.finditer(value))
    return matches


def normalize_main_software_name(value: Any) -> str:
    """Keep the software identity while removing embedded hardware descriptors."""
    name = " ".join(str(value or "").split()).strip(" :：，,；;。")

    def keep_or_remove(match: re.Match[str]) -> str:
        content = match.group(1).strip()
        return "" if any(marker in content for marker in _HARDWARE_NAME_MARKERS) else match.group(0)

    name = _HARDWARE_PARENTHESES_RE.sub(keep_or_remove, name).strip()
    return name
