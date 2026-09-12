"""第 21 层：平航事实经 canonical 模型生成现有 DTO 投影。"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

from ...repository.report.report_parse_input_models import ReportParseInputSnapshot
from .canonical_adapter_service import (
    canonical_to_inspection_report,
    inspection_report_to_canonical,
)
from .canonical_models_service import FieldProvenance


def project_pinghang_report(
    report: Mapping[str, Any], snapshot: ReportParseInputSnapshot,
) -> dict[str, Any]:
    """建立带来源的 canonical 中间态，再投影至当前审核/导出 DTO。"""
    migration = inspection_report_to_canonical(report)
    canonical = migration.canonical_case
    canonical = canonical.model_copy(update={
        "case_info": canonical.case_info.model_copy(update={
            "case_name": snapshot.case_info.get("case_name", ""),
        }),
        "inspection_period": canonical.inspection_period.model_copy(update={
            "created_at": snapshot.case_info.get("create_time", ""),
            "reported_at": snapshot.case_info.get("report_time", ""),
        }),
    })
    raw_items = {
        str(item.get("evidence_number", "")): item
        for item in (report.get("introduction") or {}).get("evidence_list") or []
        if isinstance(item, Mapping)
    }
    materials = []
    for material in canonical.materials:
        source_file = snapshot.device_source_files.get(material.evidence_number)
        provenance = _provenance(snapshot, source_file, "Rows")
        raw_item = raw_items.get(material.evidence_number, {})
        identifiers = [
            identifier.model_copy(update={"provenance": [provenance]})
            for identifier in material.identifiers
        ]
        materials.append(material.model_copy(update={
            "name": str(raw_item.get("device_name") or material.name),
            "provenance": [provenance],
            "identifiers": identifiers,
        }))
    primary = canonical.primary_software
    if primary is not None:
        primary = primary.model_copy(update={
            "provenance": [
                _provenance(snapshot, snapshot.report_source_file, "Rows")
            ],
        })
    canonical = canonical.model_copy(update={
        "materials": materials,
        "primary_software": primary,
        "provenance": [
            _provenance(snapshot, snapshot.case_source_file, "Rows"),
            _provenance(snapshot, snapshot.report_source_file, "Rows"),
        ],
    })
    projected = canonical_to_inspection_report(canonical)
    _restore_compatibility_details(projected, report)
    return projected


def _provenance(
    snapshot: ReportParseInputSnapshot, source_file: str | None, json_path: str,
) -> FieldProvenance:
    return FieldProvenance(
        source_type="report",
        source_file=(PurePosixPath(source_file).name if source_file else None),
        json_path=json_path,
        adapter=snapshot.adapter_id,
        confidence=1.0,
    )


def _restore_compatibility_details(
    projected: dict[str, Any], source: Mapping[str, Any],
) -> None:
    """保留 canonical 暂未承载、但现有审核页面仍会读取的展示字段。"""
    source_items = {
        str(item.get("evidence_number", "")): item
        for item in (source.get("introduction") or {}).get("evidence_list") or []
        if isinstance(item, Mapping)
    }
    target_items = (projected.get("introduction") or {}).get("evidence_list") or []
    for item in target_items:
        source_item = source_items.get(str(item.get("evidence_number", "")), {})
        for key in (
            "device_type", "device_name", "brand", "holder_name", "device_type_source",
        ):
            if key in source_item:
                item[key] = source_item[key]


__all__ = ["project_pinghang_report"]
