"""Layer 21：美亚 legacy/new 输入快照到 Canonical 的确定性映射。"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from ...repository.report.html_parser import format_inspection_time_range
from ...repository.report.report_parse_input_models import ReportParseInputSnapshot
from .canonical_adapter_service import canonical_to_inspection_report
from .canonical_models_service import (
    CanonicalCaseInfo,
    CanonicalCaseIntroduction,
    CanonicalInspectionCase,
    CanonicalInspectionDetails,
    CanonicalInspectionPeriod,
    FieldProvenance,
    Material,
    MaterialIdentifier,
    PrimarySoftware,
)
from ..inspection.entrust_person_service import normalize_entrust_persons
from ..inspection.material_policy_service import classify_report_material
from ..report.report_defaults_service import (
    DEFAULT_DOCUMENT_NUMBER,
    DEFAULT_HARDWARE_DEVICE,
)


def meiya_snapshot_to_canonical(
    snapshot: ReportParseInputSnapshot,
) -> CanonicalInspectionCase:
    materials: list[Material] = []
    for row in snapshot.device_rows:
        number = row["evidence_number"]
        material_id = row.get("material_id") or number
        base = snapshot.device_base_info.get(material_id) or {}
        material_facts = {
            **base,
            "device_type": base.get("device_type") or row.get("device_type", ""),
        }
        kind, classification = classify_report_material(material_facts)
        source = snapshot.device_source_files.get(material_id)
        identifiers = []
        for identifier_type in ("imei1", "imei2", "serial_number"):
            value = row.get(identifier_type, "") or base.get(identifier_type, "")
            if value:
                identifiers.append(MaterialIdentifier(
                    type=identifier_type,
                    value=value,
                    provenance=[_provenance(snapshot, source, identifier_type)],
                ))
        materials.append(Material(
            id=material_id,
            evidence_number=number,
            type=kind,
            name=base.get("device_name") or row.get("device_name", ""),
            model=base.get("model", ""),
            holder_name=row.get("holder_name") or base.get("holder_name", ""),
            extractable=True,
            identifiers=identifiers,
            classification=classification,
            provenance=[_provenance(snapshot, source, "contents")],
        ))
    main = snapshot.report_info.get("main_software") or {}
    case = snapshot.case_info
    return CanonicalInspectionCase(
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
            time_range=format_inspection_time_range(
                case.get("create_time", ""), case.get("report_time", ""),
            ),
        ),
        materials=materials,
        primary_software=PrimarySoftware(
            name=main.get("name", ""),
            version=main.get("version", ""),
            display_name=main.get("name", ""),
            confirmation_status=main.get("status", "unconfirmed"),
            candidates=main.get("candidates", []),
            provenance=[_provenance(
                snapshot, snapshot.report_source_file, "contents",
                confirmed=main.get("status") == "confirmed_by_report",
            )],
        ),
        inspection=CanonicalInspectionDetails(
            hardware_device=DEFAULT_HARDWARE_DEVICE,
        ),
        provenance=[
            _provenance(snapshot, snapshot.case_source_file, "contents"),
            _provenance(snapshot, snapshot.report_source_file, "contents"),
        ],
    )


def project_meiya_report(snapshot: ReportParseInputSnapshot) -> dict[str, Any]:
    return canonical_to_inspection_report(meiya_snapshot_to_canonical(snapshot))


def _provenance(
    snapshot: ReportParseInputSnapshot,
    source_file: str | None,
    json_path: str,
    *,
    confirmed: bool = True,
) -> FieldProvenance:
    return FieldProvenance(
        source_type="report",
        source_file=PurePosixPath(source_file).name if source_file else None,
        json_path=json_path,
        adapter=snapshot.adapter_id,
        confidence=1.0 if confirmed else None,
    )


__all__ = ["meiya_snapshot_to_canonical", "project_meiya_report"]
