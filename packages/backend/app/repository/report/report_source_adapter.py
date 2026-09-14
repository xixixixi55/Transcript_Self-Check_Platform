"""Layer 20：内置来源报告适配器的公共契约。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .report_format_adapter import ReportFormat
from .report_parse_input_models import ReportParseInputSnapshot


@dataclass(frozen=True)
class ReportAdapterMatch:
    adapter_id: str
    adapter_version: str
    report_format: ReportFormat
    structure_fingerprint: str
    source_fingerprint: str | None = None
    profile_id: str | None = None
    profile_version: int | None = None


class ReportAdapterDetectionError(ValueError):
    """不含本地路径或报告字段值的安全适配诊断。"""


class ReportSourceAdapter(Protocol):
    """来源家族实现；一个家族可以产生多个版本化 adapter id。"""

    family_id: str
    supported_adapter_ids: tuple[str, ...]
    snapshot_before_inflight: bool

    def matches(self, source_root: Path) -> bool: ...

    def detect(self, source_root: Path) -> ReportAdapterMatch: ...

    def build_snapshot(self, source_root: Path) -> ReportParseInputSnapshot: ...


__all__ = [
    "ReportAdapterDetectionError", "ReportAdapterMatch", "ReportSourceAdapter",
]
