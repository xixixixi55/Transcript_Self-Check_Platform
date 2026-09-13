"""第 20 层：平航手机多路取证报告 v1 的受限结构适配器。"""

from __future__ import annotations

import base64
import binascii
import hashlib
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .pinghang_jsonp_repository import (
    PinghangNavigationNode,
    PinghangPayloadError,
    parse_pinghang_navigation,
    parse_pinghang_payload,
)
from .report_parse_input_filesystem import (
    file_entries, require_contained_path, require_directory, require_regular_file,
)
from .report_parse_input_models import ReportParseInputError


PINGHANG_ADAPTER_ID = "pinghang-mobile-multipath-v1"
PINGHANG_ADAPTER_VERSION = "1.6.0"
PINGHANG_DEFAULT_MAIN_SOFTWARE_NAME = "平航手机多路分析取证软件"
_MAX_SELECTED_PAGES = 4096
_MAX_SELECTED_METADATA_BYTES = 32 * 1024 * 1024
_MAX_SINGLE_FILE_BYTES = 2 * 1024 * 1024
_MAX_ENTRY_FILES = 16
_CASE_REQUIRED_LABELS = {"案件名称", "案件编号"}
_CASE_LABELS = _CASE_REQUIRED_LABELS | {
    "案件类型", "创建时间", "案件描述", "调查员",
    "送检人员", "送检人", "送检单位",
}
_REPORT_LABELS = {"数据取证软件版本", "报告导出软件版本", "软件序列号", "报告完成日期"}


class PinghangReportError(ValueError):
    """识别到平航报告外壳，但内部结构不满足受支持版本。"""


@dataclass(frozen=True)
class PinghangReportFacts:
    case_info: dict[str, str]
    device_rows: tuple[dict[str, str], ...]
    report_info: dict[str, object]
    device_base_info: dict[str, dict[str, str]]
    case_source_file: str
    report_source_file: str
    device_source_files: dict[str, str]
    holder_source_files: dict[str, str]
    relative_files: tuple[str, ...]
    structure_fingerprint: str


ReadFile = Callable[[Path], bytes]


def looks_like_pinghang_report(source_root: Path) -> bool:
    return (
        (source_root / "报告" / "data" / "navigation_data.js").is_file()
        and (source_root / "报告" / "data" / "ViewData").is_dir()
    )


def parse_pinghang_report(
    source_root: Path, *, read_file: ReadFile | None = None,
) -> PinghangReportFacts:
    """读取有界元数据并映射为统一 Parser 事实，不扫描附件或资源。"""
    reader = read_file or _read_file
    report_data = source_root / "报告" / "data"
    view_root = report_data / "ViewData"
    try:
        require_contained_path(report_data, source_root)
        require_contained_path(view_root, source_root)
        require_directory(report_data)
        require_directory(view_root)
        entry_files = [
            Path(item.path) for item in file_entries(source_root)
            if item.name.casefold().endswith((".html", ".htm"))
        ]
        if not entry_files or len(entry_files) > _MAX_ENTRY_FILES:
            raise PinghangReportError("PINGHANG_ENTRY_MISSING")
        entry_matches = [
            path for path in entry_files
            if "平航手机多路取证报告" in _decode(_read_bounded(reader, path))
        ]
        if len(entry_matches) != 1:
            raise PinghangReportError("PINGHANG_ENTRY_AMBIGUOUS")

        navigation_path = report_data / "navigation_data.js"
        navigation = parse_pinghang_navigation(
            _decode(_read_bounded(reader, navigation_path))
        )
        case_nodes = [
            node for node in navigation
            if node.view_type == "Table" and _decode_node_name(node.encoded_name) == "案件信息"
        ]
        device_nodes = [node for node in navigation if node.view_type == "DeviceInfo"]
        if len(case_nodes) != 1:
            raise PinghangReportError("PINGHANG_CASE_NODE_AMBIGUOUS")
        if not device_nodes:
            raise PinghangReportError("PINGHANG_DEVICE_NODE_MISSING")
        data_indexes = [node.data_index for node in device_nodes]
        if any(not value.isdigit() for value in data_indexes) or len(set(data_indexes)) != len(data_indexes):
            raise PinghangReportError("PINGHANG_DEVICE_NODE_DUPLICATE")
        case_node = case_nodes[0]
        if not case_node.data_index.isdigit():
            raise PinghangReportError("PINGHANG_CASE_NODE_INVALID")
        owner_nodes = _owner_nodes_by_device(navigation, device_nodes)
        selected_indexes = ["0", case_node.data_index, *data_indexes]
        selected_indexes.extend(node.data_index for node in owner_nodes.values())
        if len(set(selected_indexes)) != len(selected_indexes):
            raise PinghangReportError("PINGHANG_OWNER_NODE_DUPLICATE")
        selected_keys = {("0", 1)}
        selected_keys.update(_node_page_keys(case_node))
        for node in device_nodes:
            selected_keys.update(_node_page_keys(node))
        for node in owner_nodes.values():
            selected_keys.update(_node_page_keys(node))
        if len(selected_keys) > _MAX_SELECTED_PAGES:
            raise PinghangReportError("PINGHANG_METADATA_LIMIT_EXCEEDED")
        page_paths = {
            key: view_root / f"{key[0]}_{key[1]}.json"
            for key in selected_keys
        }
        if sum(_bounded_file_size(path) for path in page_paths.values()) > _MAX_SELECTED_METADATA_BYTES:
            raise PinghangReportError("PINGHANG_METADATA_LIMIT_EXCEEDED")
        payloads = {
            key: parse_pinghang_payload(
                _decode(_read_bounded(reader, path)),
                expected_index=key[0], expected_page=key[1],
            )
            for key, path in page_paths.items()
        }
    except (OSError, UnicodeError, PinghangPayloadError, ReportParseInputError) as error:
        raise PinghangReportError("PINGHANG_METADATA_INVALID") from error

    case_fields = _combined_node_fields(case_node, payloads, expected_type="Table")
    report_payload = payloads.get(("0", 1))
    if report_payload is None or _info_type(report_payload) != "Table":
        raise PinghangReportError("PINGHANG_REPORT_PAGE_INVALID")
    report_fields = _fields(report_payload)
    if (
        not _CASE_REQUIRED_LABELS <= set(case_fields)
        or len(_REPORT_LABELS & set(report_fields)) < 2
    ):
        raise PinghangReportError("PINGHANG_SEMANTIC_PAGE_AMBIGUOUS")

    device_rows: list[dict[str, str]] = []
    device_base_info: dict[str, dict[str, str]] = {}
    device_source_files: dict[str, str] = {}
    holder_source_files: dict[str, str] = {}
    device_structure: list[str] = []
    for node in device_nodes:
        fields = _device_fields(node, payloads)
        owner_node = owner_nodes.get(node.node_id)
        owner_fields = _combined_node_fields(
            owner_node, payloads, expected_type="Table",
        ) if owner_node else {}
        evidence_number = fields.get("检材编号", "").strip()
        if not evidence_number or evidence_number in device_base_info:
            raise PinghangReportError("PINGHANG_EVIDENCE_ID_AMBIGUOUS")
        start_time = fields.get("取证开始时间", "").strip()
        end_time = fields.get("取证结束时间", "").strip()
        device_type = _normalize_pinhang_device_type(
            _first_field(fields, "数据类型", "设备类型")
        )
        device_name = _first_field(fields, "检材名称", "手机名称", "设备名称")
        base = {
            "device_name": device_name,
            "device_type": device_type,
            "brand": _first_field(fields, "设备品牌", "手机品牌"),
            "model": _first_field(fields, "设备型号", "手机型号", "手机内部型号"),
            "imei1": _first_field(fields, "IMEI", "IMEI1"),
            "imei2": _first_field(fields, "IMEI2"),
            "serial_number": _first_field(fields, "序列码", "序列号"),
            "holder_name": _first_field(owner_fields, "用户姓名"),
        }
        device_rows.append({
            "evidence_number": evidence_number,
            "device_name": device_name,
            "holder_name": base["holder_name"],
            "device_type": device_type,
            "imei1": base["imei1"],
            "imei2": base["imei2"],
            "serial_number": base["serial_number"],
            "start_time": start_time,
            "end_time": end_time,
            "time_range": f"{start_time} ~ {end_time}" if start_time and end_time else "",
            "vendor_device_name": "",
        })
        device_base_info[evidence_number] = base
        device_source_files[evidence_number] = page_paths[
            (node.data_index, 1)
        ].relative_to(source_root).as_posix()
        if owner_node:
            holder_source_files[evidence_number] = page_paths[
                (owner_node.data_index, 1)
            ].relative_to(source_root).as_posix()
        device_structure.append(
            f"{node.data_index}:{node.range_count}:" + ",".join(sorted(fields))
            + "|owner:" + ",".join(sorted(owner_fields))
        )

    relative_files = tuple(sorted({
        entry_matches[0].relative_to(source_root).as_posix(),
        navigation_path.relative_to(source_root).as_posix(),
        *(path.relative_to(source_root).as_posix() for path in page_paths.values()),
    }, key=str.casefold))
    structure = "\n".join([
        PINGHANG_ADAPTER_ID,
        PINGHANG_ADAPTER_VERSION,
        "case:" + ",".join(sorted(set(case_fields) & _CASE_LABELS)),
        "report:" + ",".join(sorted(set(report_fields) & _REPORT_LABELS)),
        *device_structure,
    ])
    return PinghangReportFacts(
        case_info={
            "case_name": case_fields.get("案件名称", ""),
            "case_number": case_fields.get("案件编号", ""),
            "collector": case_fields.get("调查员", ""),
            "collect_unit": "",
            "submit_person": _first_field(case_fields, "送检人员", "送检人"),
            "submit_unit": case_fields.get("送检单位", ""),
            "case_type": case_fields.get("案件类型", ""),
            "case_summary": case_fields.get("案件描述", ""),
            "report_time": report_fields.get("报告完成日期", ""),
            "create_time": case_fields.get("创建时间", ""),
        },
        device_rows=tuple(device_rows),
        report_info=_report_info(report_fields),
        device_base_info=device_base_info,
        case_source_file=page_paths[
            (case_node.data_index, 1)
        ].relative_to(source_root).as_posix(),
        report_source_file=page_paths[("0", 1)].relative_to(source_root).as_posix(),
        device_source_files=device_source_files,
        holder_source_files=holder_source_files,
        relative_files=relative_files,
        structure_fingerprint=hashlib.sha256(structure.encode("utf-8")).hexdigest(),
    )


def _device_fields(
    node: PinghangNavigationNode, payloads: dict[tuple[str, int], dict],
) -> dict[str, str]:
    return _combined_node_fields(node, payloads, expected_type="DeviceInfo")


def _owner_nodes_by_device(
    navigation: tuple[PinghangNavigationNode, ...],
    device_nodes: list[PinghangNavigationNode],
) -> dict[int, PinghangNavigationNode]:
    by_id = {node.node_id: node for node in navigation}
    devices_by_scope: dict[int, list[PinghangNavigationNode]] = {}
    for device in device_nodes:
        devices_by_scope.setdefault(_node_scope(device, by_id), []).append(device)
    owners_by_scope: dict[int, list[PinghangNavigationNode]] = {}
    for node in navigation:
        if node.view_type == "Table" and _decode_node_name(node.encoded_name) == "机主信息":
            owners_by_scope.setdefault(_node_scope(node, by_id), []).append(node)
    result: dict[int, PinghangNavigationNode] = {}
    for scope, owners in owners_by_scope.items():
        devices = devices_by_scope.get(scope, [])
        if not devices:
            continue
        if len(owners) != 1 or len(devices) != 1:
            raise PinghangReportError("PINGHANG_OWNER_NODE_AMBIGUOUS")
        result[devices[0].node_id] = owners[0]
    return result


def _node_scope(
    node: PinghangNavigationNode,
    by_id: dict[int, PinghangNavigationNode],
) -> int:
    current = node
    visited: set[int] = set()
    while current.parent_id in by_id:
        if current.node_id in visited:
            raise PinghangReportError("PINGHANG_NAVIGATION_CYCLE")
        visited.add(current.node_id)
        current = by_id[current.parent_id]
    return current.node_id


def _combined_node_fields(
    node: PinghangNavigationNode,
    payloads: dict[tuple[str, int], dict],
    *,
    expected_type: str,
) -> dict[str, str]:
    combined: dict[str, str] = {}
    for key in _node_page_keys(node):
        payload = payloads.get(key)
        if payload is None or _info_type(payload) != expected_type:
            raise PinghangReportError("PINGHANG_SELECTED_PAGE_INVALID")
        for label, value in _fields(payload).items():
            if label in combined and combined[label] != value:
                raise PinghangReportError("PINGHANG_SELECTED_FIELD_AMBIGUOUS")
            combined[label] = value
    return combined


def _node_page_keys(node: PinghangNavigationNode) -> set[tuple[str, int]]:
    if (
        not node.data_index.isdigit()
        or node.range_count < 1
        or node.range_count > _MAX_SELECTED_PAGES
    ):
        raise PinghangReportError("PINGHANG_NAVIGATION_RANGE_INVALID")
    return {(node.data_index, page) for page in range(1, node.range_count + 1)}


def _decode_node_name(value: str) -> str:
    try:
        return base64.b64decode(value, validate=True).decode("utf-8").strip()
    except (binascii.Error, ValueError, UnicodeError):
        return ""


def _fields(payload: dict) -> dict[str, str]:
    rows = payload.get("Rows")
    if rows is None:
        rows = payload.get("Data")
    if not isinstance(rows, list):
        raise PinghangReportError("PINGHANG_PAGE_ROWS_INVALID")
    result: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        if _info_type(payload) == "DeviceInfo":
            label, value = _cell(row.get("Val1")), _cell(row.get("Val2"))
        else:
            label, value = _cell(row.get("Val0")), _cell(row.get("Val1"))
        label = label.strip().rstrip(":：")
        if not label:
            continue
        if label in result and result[label] != value:
            raise PinghangReportError("PINGHANG_PAGE_FIELD_AMBIGUOUS")
        result[label] = value.strip()
    return result


def _cell(value: object) -> str:
    if not isinstance(value, list) or not value:
        return ""
    scalars = [str(item) for item in value if isinstance(item, (str, int, float))]
    if not scalars:
        return ""
    return scalars[1] if len(scalars) > 1 and scalars[0] in {"Text", "Link"} else scalars[0]


def _info_type(payload: dict) -> str:
    info = payload.get("Info")
    return str(info.get("type", "")).strip() if isinstance(info, dict) else ""


def _report_info(fields: dict[str, str]) -> dict[str, object]:
    acquisition_version = fields.get("数据取证软件版本", "").strip()
    export_version = fields.get("报告导出软件版本", "").strip()
    return {
        "product_version": acquisition_version,
        "platform_version": export_version,
        "main_software": {
            "name": PINGHANG_DEFAULT_MAIN_SOFTWARE_NAME,
            "version": acquisition_version,
            "status": "confirmed_by_user",
            "candidates": [],
        },
    }


def _first_field(fields: dict[str, str], *names: str) -> str:
    return next((fields[name].strip() for name in names if fields.get(name, "").strip()), "")


def _normalize_pinhang_device_type(value: str) -> str:
    """应用仅属于平航 v1 的用户确认类型映射。"""
    normalized = "".join(unicodedata.normalize("NFKC", value).split()).casefold()
    return "手机" if normalized == "android设备" else value


def _read_file(path: Path) -> bytes:
    require_regular_file(path)
    return path.read_bytes()


def _read_bounded(reader: ReadFile, path: Path) -> bytes:
    if _bounded_file_size(path) > _MAX_SINGLE_FILE_BYTES:
        raise PinghangReportError("PINGHANG_METADATA_LIMIT_EXCEEDED")
    return reader(path)


def _bounded_file_size(path: Path) -> int:
    require_regular_file(path)
    try:
        return int(path.stat().st_size)
    except OSError as error:
        raise PinghangReportError("PINGHANG_METADATA_INVALID") from error


def _decode(raw: bytes) -> str:
    return raw.decode("utf-8-sig", errors="strict")


__all__ = [
    "PINGHANG_ADAPTER_ID", "PINGHANG_ADAPTER_VERSION",
    "PINGHANG_DEFAULT_MAIN_SOFTWARE_NAME", "PinghangReportError",
    "PinghangReportFacts", "looks_like_pinghang_report", "parse_pinghang_report",
]
