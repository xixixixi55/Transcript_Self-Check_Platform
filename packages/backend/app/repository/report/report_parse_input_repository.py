"""Layer 20：通过唯一匹配来源适配器构建请求级解析快照。"""

from __future__ import annotations

from ..source.filesystem_identity_repository import resolve_directory
from .report_adapter_registry import select_report_adapter
from .report_parse_input_models import (
    DependencyRecord,
    ReportParseInputError,
    ReportParseInputSnapshot,
)


def build_report_parse_input_snapshot(source_dir: str) -> ReportParseInputSnapshot:
    """识别一个内置来源家族，并仅由所选适配器读取其核心依赖。"""
    source_root = resolve_directory(source_dir)
    adapter = select_report_adapter(source_root)
    return adapter.build_snapshot(source_root)


__all__ = [
    "DependencyRecord", "ReportParseInputError", "ReportParseInputSnapshot",
    "build_report_parse_input_snapshot",
]
