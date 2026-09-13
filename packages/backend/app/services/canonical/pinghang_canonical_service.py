"""第 21 层：平航原始事实先进入 Canonical，再生成兼容投影。"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from ...repository.report.report_parse_input_models import ReportParseInputSnapshot
from ...repository.report.html_parser import format_inspection_time_range, parse_report_datetime
from .canonical_adapter_service import canonical_to_inspection_report
from .canonical_models_service import (
    CanonicalCaseInfo, CanonicalCaseIntroduction, CanonicalInspectionCase,
    CanonicalInspectionPeriod, FieldProvenance, Material, MaterialIdentifier,
    PrimarySoftware,
)
from ..inspection.material_policy_service import classify_report_material
from ..inspection.entrust_person_service import normalize_entrust_persons
from ..report.report_defaults_service import DEFAULT_DOCUMENT_NUMBER


def pinghang_snapshot_to_canonical(snapshot: ReportParseInputSnapshot) -> CanonicalInspectionCase:
    """消费有界快照中的报告事实；不从展示 DTO 反推原始事实。"""
    materials = []
    for row in snapshot.device_rows:
        number = row["evidence_number"]
        base = snapshot.device_base_info[number]
        source = snapshot.device_source_files.get(number)
        kind, classification = classify_report_material(base)
        holder_source = snapshot.holder_source_files.get(number)
        materials.append(Material(
            id=number, evidence_number=number, type=kind,
            name=base.get("device_name", ""), model=base.get("model", ""),
            holder_name=base.get("holder_name", ""),
            acquisition_started_at=row.get("start_time", ""),
            acquisition_ended_at=row.get("end_time", ""),
            holder_provenance=[_provenance(snapshot, holder_source, "用户姓名")] if holder_source else [],
            extractable=True, classification=classification,
            identifiers=[MaterialIdentifier(
                type=key, value=base[key], provenance=[_provenance(snapshot, source, key)],
            ) for key in ("imei1", "imei2", "serial_number") if base.get(key)],
            provenance=[_provenance(snapshot, source, "Rows")],
        ))
    main = snapshot.report_info.get("main_software") or {}
    primary_provenance = []
    if main.get("status") == "confirmed_by_user":
        primary_provenance.append(FieldProvenance(
            source_type="user", adapter=snapshot.adapter_id, confidence=1.0,
        ))
    primary_provenance.append(_provenance(snapshot, snapshot.report_source_file, "Rows"))
    case = snapshot.case_info
    return CanonicalInspectionCase(
        case_info=CanonicalCaseInfo(
            title="电子数据检查笔录", document_number=DEFAULT_DOCUMENT_NUMBER,
            case_name=case.get("case_name", ""), case_number=case.get("case_number", ""),
            introduction=CanonicalCaseIntroduction(
                entrust_unit=case.get("submit_unit", ""),
                entrust_persons=normalize_entrust_persons(case.get("submit_person", "")),
                case_summary=case.get("case_summary", ""),
            ),
        ),
        inspection_period=CanonicalInspectionPeriod(
            created_at=case.get("create_time", ""), reported_at=case.get("report_time", ""),
            time_range=_acquisition_time_range(materials),
        ),
        materials=materials,
        primary_software=PrimarySoftware(
            name=main.get("name", ""), version=main.get("version", ""),
            display_name=main.get("name", ""),
            confirmation_status=main.get("status", "unconfirmed"),
            candidates=main.get("candidates", []), provenance=primary_provenance,
        ),
        provenance=[_provenance(snapshot, snapshot.case_source_file, "Rows"),
                    _provenance(snapshot, snapshot.report_source_file, "Rows")],
    )


def project_pinghang_report(snapshot: ReportParseInputSnapshot) -> dict[str, Any]:
    """投影规范事实；流程文本、展示名称和环境初值由共用 Parser 补齐。"""
    canonical = pinghang_snapshot_to_canonical(snapshot)
    projected = canonical_to_inspection_report(canonical)
    for item, material in zip(projected["introduction"]["evidence_list"], canonical.materials):
        item["holder_name"] = material.holder_name
    return projected


def _provenance(snapshot: ReportParseInputSnapshot, source_file: str | None,
                json_path: str) -> FieldProvenance:
    return FieldProvenance(
        source_type="report", source_file=PurePosixPath(source_file).name if source_file else None,
        json_path=json_path, adapter=snapshot.adapter_id, confidence=1.0,
    )


def _acquisition_time_range(materials: list[Material]) -> str:
    if not materials:
        return ""
    starts, ends = [], []
    for material in materials:
        start = parse_report_datetime(material.acquisition_started_at)
        end = parse_report_datetime(material.acquisition_ended_at)
        if start is None or end is None or start > end:
            return ""
        starts.append(start)
        ends.append(end)
    return format_inspection_time_range(
        min(starts).strftime("%Y-%m-%d %H:%M:%S"),
        max(ends).strftime("%Y-%m-%d %H:%M:%S"),
    )


__all__ = ["pinghang_snapshot_to_canonical", "project_pinghang_report"]
