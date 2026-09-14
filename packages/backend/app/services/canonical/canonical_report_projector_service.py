"""Layer 21：内置来源适配器到 Canonical 兼容投影的注册表。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ...repository.report.meiya_report_source_adapter import (
    MEIYA_LEGACY_ADAPTER_ID,
    MEIYA_NEW_ADAPTER_ID,
)
from ...repository.report.pinghang_report_adapter import PINGHANG_ADAPTER_ID
from ...repository.report.qianxin_report_source_adapter import QIANXIN_ADAPTER_ID
from ...repository.report.report_parse_input_models import ReportParseInputSnapshot
from ...repository.report.report_profile_repository import REPORT_PROFILE_ADAPTER_ID
from .meiya_canonical_service import project_meiya_report
from .pinghang_canonical_service import project_pinghang_report
from .qianxin_canonical_service import project_qianxin_report
from .report_profile_canonical_service import project_report_profile


@dataclass(frozen=True)
class CanonicalReportProjector:
    adapter_ids: tuple[str, ...]
    project: Callable[[ReportParseInputSnapshot], dict[str, Any]]
    material_overlay: bool = False
    replace_primary_software: bool = False
    replace_introduction: bool = False


@dataclass(frozen=True)
class CanonicalReportProjection:
    report: dict[str, Any]
    material_overlay: bool
    replace_primary_software: bool
    replace_introduction: bool


_BUILTIN_PROJECTORS = (
    CanonicalReportProjector(
        adapter_ids=(MEIYA_LEGACY_ADAPTER_ID, MEIYA_NEW_ADAPTER_ID),
        project=project_meiya_report,
    ),
    CanonicalReportProjector(
        adapter_ids=(PINGHANG_ADAPTER_ID,),
        project=project_pinghang_report,
        material_overlay=True,
        replace_primary_software=True,
        replace_introduction=True,
    ),
    CanonicalReportProjector(
        adapter_ids=(QIANXIN_ADAPTER_ID,),
        project=project_qianxin_report,
        material_overlay=True,
        replace_primary_software=True,
        replace_introduction=True,
    ),
    CanonicalReportProjector(
        adapter_ids=(REPORT_PROFILE_ADAPTER_ID,),
        project=project_report_profile,
        material_overlay=True,
        replace_primary_software=True,
        replace_introduction=True,
    ),
)


def project_report_snapshot(snapshot: ReportParseInputSnapshot) -> CanonicalReportProjection:
    matches = [
        projector for projector in _BUILTIN_PROJECTORS
        if snapshot.adapter_id in projector.adapter_ids
    ]
    if len(matches) != 1:
        raise ValueError("REPORT_CANONICAL_PROJECTOR_NOT_FOUND")
    projector = matches[0]
    return CanonicalReportProjection(
        report=projector.project(snapshot),
        material_overlay=projector.material_overlay,
        replace_primary_software=projector.replace_primary_software,
        replace_introduction=projector.replace_introduction,
    )


def registered_canonical_adapter_ids() -> tuple[str, ...]:
    """返回与内置来源注册表一一对应的 projector 身份。"""
    return tuple(
        adapter_id
        for projector in _BUILTIN_PROJECTORS
        for adapter_id in projector.adapter_ids
        if adapter_id != REPORT_PROFILE_ADAPTER_ID
    )


__all__ = [
    "CanonicalReportProjection", "CanonicalReportProjector", "project_report_snapshot",
    "registered_canonical_adapter_ids",
]
