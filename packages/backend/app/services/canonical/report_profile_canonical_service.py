"""Layer 21：已确认通用 ReportProfile 快照到 Canonical 的确定性映射。"""

from __future__ import annotations

from typing import Any

from ...repository.report.html_parser import format_inspection_time_range, parse_report_datetime
from ...repository.report.report_parse_input_models import ReportParseInputSnapshot
from .canonical_adapter_service import canonical_to_inspection_report
from .canonical_models_service import (
    CanonicalCaseInfo, CanonicalCaseIntroduction, CanonicalInspectionCase,
    CanonicalInspectionDetails, CanonicalInspectionPeriod, FieldProvenance,
    Material, MaterialIdentifier, PrimarySoftware,
)
from ..inspection.entrust_person_service import normalize_entrust_persons
from ..inspection.material_policy_service import classify_report_material
from ..report.report_defaults_service import DEFAULT_DOCUMENT_NUMBER


def project_report_profile(snapshot: ReportParseInputSnapshot) -> dict[str, Any]:
    case = snapshot.case_info
    materials: list[Material] = []
    for row in snapshot.device_rows:
        material_id = row.get("material_id") or row.get("evidence_number", "")
        base = snapshot.device_base_info.get(material_id) or {}
        kind, classification = classify_report_material({
            **base, "device_type_source": "report_field",
        })
        materials.append(Material(
            id=material_id,
            evidence_number=row.get("evidence_number", ""),
            type=kind,
            name=base.get("device_name", ""),
            model=base.get("model", ""),
            holder_name=base.get("holder_name", ""),
            acquisition_started_at=row.get("start_time", ""),
            acquisition_ended_at=row.get("end_time", ""),
            holder_provenance=[_field_provenance(snapshot, "material.holder_name")]
            if base.get("holder_name") else [],
            extractable=True,
            identifiers=[
                MaterialIdentifier(
                    type=key, value=base[key],
                    provenance=[_field_provenance(snapshot, f"material.{key}")],
                )
                for key in ("imei1", "imei2", "serial_number") if base.get(key)
            ],
            provenance=_field_provenances(snapshot, (
                "material.evidence_number", "material.name", "material.model",
                "material.acquisition_started_at", "material.acquisition_ended_at",
                "material.type",
            )),
            classification=classification,
        ))
    main = snapshot.report_info.get("main_software") or {}
    canonical = CanonicalInspectionCase(
        case_info=CanonicalCaseInfo(
            title="电子数据检查笔录",
            document_number=DEFAULT_DOCUMENT_NUMBER,
            case_name=case.get("case_name", ""),
            case_number=case.get("case_number", ""),
            introduction=CanonicalCaseIntroduction(
                entrust_unit=case.get("submit_unit", ""),
                entrust_persons=normalize_entrust_persons(case.get("submit_person", "")),
                case_summary=case.get("case_summary", ""),
            ),
        ),
        inspection_period=CanonicalInspectionPeriod(
            created_at=case.get("create_time", ""),
            reported_at=case.get("report_time", ""),
            time_range=_time_range(materials),
        ),
        materials=materials,
        primary_software=PrimarySoftware(
            name=main.get("name", ""),
            version=main.get("version", ""),
            display_name=main.get("name", ""),
            confirmation_status=main.get("status", "unconfirmed"),
            provenance=_field_provenances(
                snapshot, ("software.name", "software.version"),
            ),
        ),
        inspection=CanonicalInspectionDetails(
            hardware_device=str(snapshot.report_info.get("hardware_device") or ""),
        ),
        provenance=_field_provenances(snapshot, (
            "case.case_name", "case.case_number", "case.entrust_unit",
            "case.entrust_persons", "case.case_summary", "case.created_at",
            "case.reported_at",
        )),
    )
    report = canonical_to_inspection_report(canonical)
    for item, material in zip(report["introduction"]["evidence_list"], materials):
        item["holder_name"] = material.holder_name
    return report


def _field_provenance(
    snapshot: ReportParseInputSnapshot, canonical_field: str,
) -> FieldProvenance:
    mapping = snapshot.field_mappings.get(canonical_field) or {}
    return FieldProvenance(
        source_type="report",
        source_file=str(mapping.get("source_file") or "") or None,
        json_path=str(mapping.get("json_path") or "") or None,
        adapter=snapshot.adapter_id,
        confidence=float(mapping.get("confidence", 0)),
    )


def _field_provenances(
    snapshot: ReportParseInputSnapshot, canonical_fields: tuple[str, ...],
) -> list[FieldProvenance]:
    return [
        _field_provenance(snapshot, field)
        for field in canonical_fields if field in snapshot.field_mappings
    ]


def _time_range(materials: list[Material]) -> str:
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


__all__ = ["project_report_profile"]
