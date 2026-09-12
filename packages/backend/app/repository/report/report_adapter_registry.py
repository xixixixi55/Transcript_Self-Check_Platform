"""第 20 层：报告目录适配器唯一匹配注册表。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ..source.filesystem_identity_repository import resolve_directory
from .pinghang_report_adapter import (
    PINGHANG_ADAPTER_ID,
    PINGHANG_ADAPTER_VERSION,
    PinghangReportError,
    looks_like_pinghang_report,
    parse_pinghang_report,
)
from .report_format_adapter import ReportFormat, require_supported_report_format


@dataclass(frozen=True)
class ReportAdapterMatch:
    adapter_id: str
    adapter_version: str
    report_format: ReportFormat
    structure_fingerprint: str


class ReportAdapterDetectionError(ValueError):
    """不含本地路径或报告字段值的安全适配诊断。"""


def detect_report_adapter(source_dir: str | Path) -> ReportAdapterMatch:
    root = resolve_directory(source_dir)
    matches: list[ReportAdapterMatch] = []
    current_data = root / "data"
    current_core = (
        "data_case_info.json", "data_device_lists.json", "data_report_info.json",
    )
    if current_data.is_dir() and all((current_data / name).is_file() for name in current_core):
        try:
            report_format = require_supported_report_format(str(current_data))
        except ValueError as error:
            raise ReportAdapterDetectionError("REPORT_ADAPTER_STRUCTURE_INVALID") from error
        adapter_id = f"meiya-{report_format.value}-v1"
        matches.append(ReportAdapterMatch(
            adapter_id=adapter_id,
            adapter_version="1.0.0",
            report_format=report_format,
            structure_fingerprint=hashlib.sha256(adapter_id.encode("ascii")).hexdigest(),
        ))
    if looks_like_pinghang_report(root):
        try:
            facts = parse_pinghang_report(root)
        except PinghangReportError as error:
            raise ReportAdapterDetectionError("REPORT_ADAPTER_STRUCTURE_INVALID") from error
        matches.append(ReportAdapterMatch(
            adapter_id=PINGHANG_ADAPTER_ID,
            adapter_version=PINGHANG_ADAPTER_VERSION,
            report_format=ReportFormat.PINGHANG,
            structure_fingerprint=facts.structure_fingerprint,
        ))
    if not matches:
        raise ReportAdapterDetectionError("REPORT_ADAPTER_NOT_FOUND")
    if len(matches) != 1:
        raise ReportAdapterDetectionError("REPORT_ADAPTER_AMBIGUOUS")
    return matches[0]


__all__ = [
    "ReportAdapterDetectionError", "ReportAdapterMatch", "detect_report_adapter",
]
