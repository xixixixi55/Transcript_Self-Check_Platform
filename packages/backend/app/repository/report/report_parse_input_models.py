"""单个报告 Parser 输入快照的内部模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .report_format_adapter import ReportFormat


class ReportParseInputError(ValueError):
    """无效或不稳定解析器输入快照的安全诊断。"""


@dataclass(frozen=True)
class DependencyRecord:
    relative_path: str
    size_bytes: int
    modified_time_ns: int
    stable_identity: str
    content_digest: str


@dataclass(frozen=True)
class ReportParseInputSnapshot:
    """内部解析状态；绝不序列化到报告或公开响应中。"""

    source_key: str
    report_format: ReportFormat
    adapter_id: str
    adapter_version: str
    structure_fingerprint: str
    case_info: dict[str, str]
    device_rows: tuple[dict[str, str], ...]
    report_info: dict[str, Any]
    case_source_file: str
    report_source_file: str
    device_source_files: dict[str, str]
    evidence_directories: dict[str, str]
    device_base_info: dict[str, dict[str, str]]
    dependencies: tuple[DependencyRecord, ...]
    dependency_fingerprint: str
    holder_source_files: dict[str, str] = field(default_factory=dict)


__all__ = [
    "DependencyRecord", "ReportParseInputError", "ReportParseInputSnapshot",
]
