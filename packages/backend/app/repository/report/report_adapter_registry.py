"""Layer 20：内置来源报告适配器的唯一匹配注册表。"""

from __future__ import annotations

from pathlib import Path

from ..source.filesystem_identity_repository import resolve_directory
from .meiya_report_source_adapter import MEIYA_REPORT_SOURCE_ADAPTER
from .pinghang_report_source_adapter import PINGHANG_REPORT_SOURCE_ADAPTER
from .qianxin_report_source_adapter import QIANXIN_REPORT_SOURCE_ADAPTER
from .report_source_adapter import (
    ReportAdapterDetectionError,
    ReportAdapterMatch,
    ReportSourceAdapter,
)

_BUILTIN_REPORT_ADAPTERS: tuple[ReportSourceAdapter, ...] = (
    MEIYA_REPORT_SOURCE_ADAPTER,
    PINGHANG_REPORT_SOURCE_ADAPTER,
    QIANXIN_REPORT_SOURCE_ADAPTER,
)


def select_report_adapter(source_dir: str | Path) -> ReportSourceAdapter:
    """只按有界入口结构选择来源家族；无匹配或并列匹配均安全失败。"""
    root = resolve_directory(source_dir)
    matches = [adapter for adapter in _BUILTIN_REPORT_ADAPTERS if adapter.matches(root)]
    if not matches:
        raise ReportAdapterDetectionError("REPORT_ADAPTER_NOT_FOUND")
    if len(matches) != 1:
        raise ReportAdapterDetectionError("REPORT_ADAPTER_AMBIGUOUS")
    return matches[0]


def detect_report_adapter(source_dir: str | Path) -> ReportAdapterMatch:
    root = resolve_directory(source_dir)
    return select_report_adapter(root).detect(root)


def registered_report_adapter_ids() -> tuple[str, ...]:
    """供能力展示和契约回归使用的稳定内置格式身份。"""
    return tuple(
        adapter_id
        for adapter in _BUILTIN_REPORT_ADAPTERS
        for adapter_id in adapter.supported_adapter_ids
    )


__all__ = [
    "ReportAdapterDetectionError", "ReportAdapterMatch", "detect_report_adapter",
    "registered_report_adapter_ids", "select_report_adapter",
]
