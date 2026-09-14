"""Layer 20：奇安信网页版报告 v1 的有界来源适配器。"""

from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from ..source.filesystem_identity_repository import normalized_directory_key
from .qianxin_jsonp_repository import QianxinPayloadError, parse_qianxin_payload
from .report_format_adapter import ReportFormat
from .report_parse_input_filesystem import (
    file_entries,
    file_identity,
    fingerprint_dependencies,
    read_bounded_dependency,
    require_directory,
    require_regular_file,
    stable_identity,
)
from .report_parse_input_models import (
    DependencyRecord,
    ReportParseInputError,
    ReportParseInputSnapshot,
)
from .report_source_adapter import ReportAdapterDetectionError, ReportAdapterMatch


QIANXIN_ADAPTER_ID = "qianxin-web-report-v1"
QIANXIN_ADAPTER_VERSION = "1.0.0"
_REPORT_PROFILE = "data_report_profile.json"
_NAVIGATION = "data_navigation.json"
_PACKAGE_RE = re.compile(r"data_package_profile_(?P<index>\d+)\.json\Z")
_MAX_HTML_BYTES = 4 * 1024 * 1024
_MAX_PROFILE_BYTES = 512 * 1024
_MAX_NAVIGATION_BYTES = 2 * 1024 * 1024
_MAX_PACKAGES = 256
_HTML_MARKERS = (
    "static.report.context", "data_report_profile",
    "data_package_profile", "data_navigation",
)


class QianxinReportSourceAdapter:
    family_id = QIANXIN_ADAPTER_ID
    supported_adapter_ids = (QIANXIN_ADAPTER_ID,)
    snapshot_before_inflight = True

    def matches(self, source_root: Path) -> bool:
        data_root = source_root / "data"
        if not data_root.is_dir():
            return False
        if not all((data_root / name).is_file() for name in (_REPORT_PROFILE, _NAVIGATION)):
            return False
        try:
            with os.scandir(source_root) as root_entries:
                has_html = any(
                    entry.name.casefold().endswith(".html")
                    for entry in root_entries
                    if entry.is_file(follow_symlinks=False)
                )
            with os.scandir(data_root) as data_entries:
                has_package = any(
                    _PACKAGE_RE.fullmatch(entry.name) is not None
                    for entry in data_entries
                    if entry.is_file(follow_symlinks=False)
                )
        except OSError:
            return False
        return has_html and has_package

    def detect(self, source_root: Path) -> ReportAdapterMatch:
        try:
            snapshot = self.build_snapshot(source_root)
        except (QianxinPayloadError, ReportParseInputError, ValueError) as error:
            raise ReportAdapterDetectionError("REPORT_ADAPTER_STRUCTURE_INVALID") from error
        return ReportAdapterMatch(
            adapter_id=QIANXIN_ADAPTER_ID,
            adapter_version=QIANXIN_ADAPTER_VERSION,
            report_format=ReportFormat.QIANXIN,
            structure_fingerprint=snapshot.structure_fingerprint,
            source_fingerprint=snapshot.dependency_fingerprint,
        )

    def build_snapshot(self, source_root: Path) -> ReportParseInputSnapshot:
        require_directory(source_root)
        data_root = source_root / "data"
        require_directory(data_root)
        dependencies: dict[str, DependencyRecord] = {}
        html_path = _select_entry_html(source_root)
        _validate_html(_read_limited(
            html_path, source_root, dependencies, _MAX_HTML_BYTES,
        ))
        data_files = file_entries(data_root)
        by_name = {entry.name: Path(entry.path) for entry in data_files}
        report_payload = _read_payload(
            by_name.get(_REPORT_PROFILE), source_root, dependencies,
            "data_report_profile", _MAX_PROFILE_BYTES,
        )
        navigation_payload = _read_payload(
            by_name.get(_NAVIGATION), source_root, dependencies,
            "data_navigation", _MAX_NAVIGATION_BYTES,
        )
        _validate_navigation(navigation_payload)
        case_info, report_info = _map_report_profile(report_payload)

        packages = _select_packages(data_files)
        rows: list[dict[str, str]] = []
        bases: dict[str, dict[str, str]] = {}
        sources: dict[str, str] = {}
        seen_evidence_numbers: set[str] = set()
        for index, path in packages:
            stem = path.stem
            payload = _read_payload(
                path, source_root, dependencies, stem, _MAX_PROFILE_BYTES,
            )
            row, base = _map_package_profile(payload, index)
            evidence_number = row["evidence_number"]
            folded_number = evidence_number.casefold()
            if folded_number and folded_number in seen_evidence_numbers:
                raise ReportParseInputError("奇安信报告包含重复检材编号。")
            if folded_number:
                seen_evidence_numbers.add(folded_number)
            material_id = row["material_id"]
            rows.append(row)
            bases[material_id] = base
            sources[material_id] = f"data/{path.name}"

        structure_fingerprint = hashlib.sha256(
            QIANXIN_ADAPTER_ID.encode("ascii")
        ).hexdigest()
        records = tuple(sorted(
            dependencies.values(), key=lambda item: item.relative_path.casefold(),
        ))
        return ReportParseInputSnapshot(
            source_key=normalized_directory_key(str(source_root)),
            report_format=ReportFormat.QIANXIN,
            adapter_id=QIANXIN_ADAPTER_ID,
            adapter_version=QIANXIN_ADAPTER_VERSION,
            structure_fingerprint=structure_fingerprint,
            case_info=case_info,
            device_rows=tuple(rows),
            report_info=report_info,
            case_source_file="data/data_report_profile.json",
            report_source_file="data/data_report_profile.json",
            device_source_files=sources,
            evidence_directories={},
            device_base_info=bases,
            dependencies=records,
            dependency_fingerprint=fingerprint_dependencies(
                records, QIANXIN_ADAPTER_ID, QIANXIN_ADAPTER_VERSION,
                structure_fingerprint,
            ),
            parsed_files=("report_profile", "navigation", "package_profiles"),
            preserve_material_order=True,
        )


def _select_entry_html(source_root: Path) -> Path:
    candidates = [
        Path(entry.path) for entry in file_entries(source_root)
        if Path(entry.name).suffix.casefold() == ".html"
    ]
    if len(candidates) != 1:
        raise ReportParseInputError("奇安信报告入口不唯一。")
    return candidates[0]


def _select_packages(entries: list[os.DirEntry[str]]) -> list[tuple[int, Path]]:
    result: list[tuple[int, Path]] = []
    indexes: set[int] = set()
    for entry in entries:
        match = _PACKAGE_RE.fullmatch(entry.name)
        if match is None:
            continue
        index = int(match.group("index"))
        if index in indexes:
            raise ReportParseInputError("奇安信报告包索引重复。")
        indexes.add(index)
        result.append((index, Path(entry.path)))
    if not result or len(result) > _MAX_PACKAGES:
        raise ReportParseInputError("奇安信报告检材数量不受支持。")
    return sorted(result, key=lambda item: item[0])


def _read_limited(
    path: Path | None,
    source_root: Path,
    dependencies: dict[str, DependencyRecord],
    limit: int,
) -> bytes:
    if path is None:
        raise ReportParseInputError("奇安信报告核心元数据缺失。")
    require_regular_file(path)
    try:
        expected_identity = file_identity(path.lstat())
        raw, details = read_bounded_dependency(
            path, source_root, limit, expected_identity=expected_identity,
        )
        relative = path.relative_to(source_root).as_posix()
    except (OSError, ValueError) as error:
        raise ReportParseInputError("奇安信报告核心元数据无法读取。") from error
    dependencies[relative.casefold()] = DependencyRecord(
        relative_path=relative,
        size_bytes=int(details.st_size),
        modified_time_ns=int(details.st_mtime_ns),
        stable_identity=stable_identity(details),
        content_digest=hashlib.sha256(raw).hexdigest(),
    )
    return raw


def _read_payload(
    path: Path | None,
    source_root: Path,
    dependencies: dict[str, DependencyRecord],
    stem: str,
    limit: int,
) -> Any:
    raw = _read_limited(path, source_root, dependencies, limit)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ReportParseInputError("奇安信报告核心元数据编码无效。") from error
    return parse_qianxin_payload(text, expected_stem=stem)


def _validate_html(raw: bytes) -> None:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ReportParseInputError("奇安信报告入口编码无效。") from error
    lowered = text.casefold()
    if "<html" not in lowered or not all(marker in text for marker in _HTML_MARKERS):
        raise ReportParseInputError("奇安信报告入口结构无效。")


def _validate_navigation(value: Any) -> None:
    required = {"id", "pid", "name", "contextConfig", "parserConfig"}
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(node, dict) or not required.issubset(node) for node in value)
    ):
        raise ReportParseInputError("奇安信报告导航结构无效。")


def _map_report_profile(value: Any) -> tuple[dict[str, str], dict[str, Any]]:
    if not isinstance(value, dict) or not isinstance(value.get("source"), dict):
        raise ReportParseInputError("奇安信报告信息结构无效。")
    case = _pair_map(value.get("caseInfo"), required={"案件名称", "创建时间"})
    source = value["source"]
    software_name = _text(source.get("name"))
    software_version = _text(source.get("appVersion"))
    if not software_name or not software_version:
        raise ReportParseInputError("奇安信报告主软件信息无效。")
    return ({
        "case_name": case.get("案件名称", ""),
        "case_number": case.get("案件编号", ""),
        "submit_person": case.get("送检人", ""),
        "submit_unit": case.get("送检人单位", ""),
        "case_summary": "",
        "create_time": _normalize_datetime(case.get("创建时间", "")),
        "report_time": _normalize_datetime(_text(value.get("createTime"))),
    }, {
        "product_version": software_version,
        "platform_version": _text(source.get("platformVersion")),
        "main_software": {
            "name": software_name,
            "version": software_version,
            "status": "confirmed_by_report",
            "candidates": [],
        },
    })


def _map_package_profile(
    value: Any, index: int,
) -> tuple[dict[str, str], dict[str, str]]:
    if not isinstance(value, dict):
        raise ReportParseInputError("奇安信检材信息结构无效。")
    info = _pair_map(
        value.get("info"),
        required={"检材编号", "检材平台", "提取时间", "解析时间"},
    )
    device = _pair_map(value.get("deviceInfo"), required={"设备名称", "型号"})
    material_id = f"qianxin-package-{index}"
    imei1 = _identifier(info.get("IMEI1")) or _identifier(device.get("IMEI"))
    imei2 = _identifier(info.get("IMEI2"))
    serial_number = _text(device.get("序列号")) or _text(device.get("Mtp序列号"))
    row = {
        "material_id": material_id,
        "evidence_number": info.get("检材编号", ""),
        "device_type": info.get("检材平台", ""),
        "device_name": device.get("设备名称", ""),
        "holder_name": info.get("机主姓名", ""),
        "imei1": imei1,
        "imei2": imei2,
        "serial_number": serial_number,
        "start_time": _normalize_datetime(info.get("提取时间", "")),
        "end_time": _normalize_datetime(info.get("解析时间", "")),
    }
    base = {
        "device_type": row["device_type"],
        "device_name": row["device_name"],
        "brand": device.get("品牌", ""),
        "model": device.get("型号", "") or info.get("手机型号", ""),
        "holder_name": row["holder_name"],
        "imei1": imei1,
        "imei2": imei2,
        "serial_number": serial_number,
    }
    return row, base


def _pair_map(value: Any, *, required: set[str]) -> dict[str, str]:
    if not isinstance(value, list):
        raise ReportParseInputError("奇安信报告字段列表无效。")
    result: dict[str, str] = {}
    for item in value:
        if not isinstance(item, dict):
            raise ReportParseInputError("奇安信报告字段列表无效。")
        key = _text(item.get("key"))
        if not key or key in result:
            raise ReportParseInputError("奇安信报告字段标签无效。")
        result[key] = _text(item.get("value"))
    if not required.issubset(result):
        raise ReportParseInputError("奇安信报告必需字段缺失。")
    return result


def _text(value: Any) -> str:
    if value is None or isinstance(value, (dict, list, tuple, set, bool)):
        return ""
    return str(value).strip()


def _identifier(value: Any) -> str:
    text = _text(value)
    return text if re.fullmatch(r"\d{15}", text) else ""


def _normalize_datetime(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    parsed = None
    for pattern in ("%Y/%m/%d %H:%M:%S %z", "%Y-%m-%d %H:%M:%S %z"):
        try:
            parsed = datetime.strptime(text, pattern)
            break
        except ValueError:
            continue
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return text
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


QIANXIN_REPORT_SOURCE_ADAPTER = QianxinReportSourceAdapter()

__all__ = [
    "QIANXIN_ADAPTER_ID", "QIANXIN_ADAPTER_VERSION",
    "QIANXIN_REPORT_SOURCE_ADAPTER", "QianxinReportSourceAdapter",
]
