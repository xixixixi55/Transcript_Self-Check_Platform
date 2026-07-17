"""Adapters between report formats and the canonical inspection model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from .canonical_models_service import (
    CanonicalCaseInfo,
    CanonicalInspectionCase,
    CanonicalInspectionDetails,
    CanonicalInspectionPeriod,
    FieldProvenance,
    InspectorSnapshot,
    Material,
    MaterialIdentifier,
    SoftwareTool,
)


class ReportAdapter(Protocol):
    """Future adapter contract for report structure discovery and parsing."""

    adapter_id: str

    def detect(self, report: Mapping[str, Any]) -> float: ...

    def discover(self, report: Mapping[str, Any]) -> list[FieldProvenance]: ...

    def parse(self, report: Mapping[str, Any]) -> CanonicalInspectionCase: ...


@dataclass(frozen=True)
class LegacyMigrationResult:
    canonical_case: CanonicalInspectionCase
    missing_fields: tuple[str, ...]
    diagnostic_codes: tuple[str, ...]


def _text(value: Any, default: str = "") -> str:
    """Convert optional legacy values without manufacturing the text ``None``."""
    return default if value is None else str(value)


def _first_identifier(material: Material, identifier_type: str) -> str:
    for identifier in material.identifiers:
        if identifier.type == identifier_type:
            return identifier.value
    return ""


def _software_tools(case: CanonicalInspectionCase) -> list[dict[str, str]]:
    return [
        {"name": tool.name, "version": tool.version}
        for tool in case.software_tools
    ]


def _primary_software(case: CanonicalInspectionCase) -> tuple[str, str]:
    for tool in case.software_tools:
        if tool.category == "main_forensic":
            return tool.name, tool.version
    return "", ""


def canonical_to_inspection_report(case: CanonicalInspectionCase) -> dict[str, Any]:
    """Create the existing public DTO projection without applying display rules."""

    intro = case.case_info.introduction
    evidence_list = [
        {
            "id": material.id,
            "device_type": material.name or material.type,
            "model": material.model,
            "imei1": _first_identifier(material, "imei1"),
            "imei2": _first_identifier(material, "imei2"),
            "serial_number": _first_identifier(material, "serial_number"),
            "evidence_number": material.evidence_number,
        }
        for material in case.materials
    ]
    inspectors = [
        {
            "name": inspector.name,
            "unit": inspector.unit,
            "badge_number": inspector.police_number,
        }
        for inspector in case.inspectors
    ]
    result = case.inspection.result
    primary_software_name, primary_software_version = _primary_software(case)
    return {
        "title": case.case_info.title,
        "document_number": case.case_info.document_number,
        "case_number": case.case_info.case_number,
        "introduction": {
            "entrust_unit": intro.entrust_unit,
            "entrust_persons": list(intro.entrust_persons),
            "entrust_time": intro.entrust_time,
            "case_summary": intro.case_summary,
            "evidence_list": evidence_list,
            "inspection_requirement": intro.inspection_requirement,
            "inspection_time_range": case.inspection_period.time_range,
            "inspectors": inspectors,
            "inspection_place": intro.inspection_place,
        },
        "inspection": {
            "method": case.inspection.method,
            "hardware_device": case.inspection.hardware_device,
            "software_tools": _software_tools(case),
            "process_steps": list(case.inspection.process_steps),
            "result": {
                "evidence_number": result.evidence_number,
                "software_name": primary_software_name,
                "software_version": primary_software_version,
                "data_summary": result.data_summary,
                "rar_filename": result.rar_filename,
                "md5_hash": result.md5_hash,
                "file_size": result.file_size,
            },
        },
        "attachments": {
            "extract_list": dict(case.attachments.extract_list),
            "photo_ids": list(case.attachments.photo_ids),
            "disc_number": case.attachments.disc_number,
            "burning_date": case.attachments.burning_date,
        },
    }


def _provenance(path: str) -> FieldProvenance:
    return FieldProvenance(
        source_type="legacy_migration",
        adapter="legacy-report-input",
        json_path=path,
    )


def inspection_report_to_canonical(
    report: Mapping[str, Any],
) -> LegacyMigrationResult:
    """Best-effort legacy migration; it intentionally does not promise losslessness."""

    introduction = report.get("introduction") or {}
    inspection = report.get("inspection") or {}
    raw_evidence = introduction.get("evidence_list") or []
    materials: list[Material] = []
    for index, item in enumerate(raw_evidence):
        identifiers: list[MaterialIdentifier] = []
        for identifier_type in ("imei1", "imei2", "serial_number"):
            value = _text(item.get(identifier_type))
            if value:
                identifiers.append(
                    MaterialIdentifier(
                        type=identifier_type,
                        value=value,
                        provenance=[_provenance(f"introduction.evidence_list[{index}].{identifier_type}")],
                    )
                )
        materials.append(
            Material(
                id=_text(item.get("id"), f"legacy-material-{index + 1}"),
                evidence_number=_text(item.get("evidence_number")),
                name=_text(item.get("device_type")),
                model=_text(item.get("model")),
                identifiers=identifiers,
                provenance=[_provenance(f"introduction.evidence_list[{index}].device_type")],
            )
        )

    inspectors = [
        InspectorSnapshot(
            name=_text(item.get("name")),
            unit=_text(item.get("unit")),
            police_number=_text(item.get("badge_number")),
            selected_order=index,
        )
        for index, item in enumerate(introduction.get("inspectors") or [])
    ]
    software_tools = [
        SoftwareTool(
            category="unclassified",
            name=_text(item.get("name")),
            version=_text(item.get("version")),
            display_name=_text(item.get("name")),
        )
        for item in inspection.get("software_tools") or []
    ]
    result = inspection.get("result") or {}
    result_software_name = _text(result.get("software_name"))
    result_software_version = _text(result.get("software_version"))
    if result_software_name and not software_tools:
        software_tools.append(
            SoftwareTool(
                category="main_forensic",
                name=result_software_name,
                version=result_software_version,
                display_name=result_software_name,
            )
        )
    case_info = CanonicalCaseInfo(
        title=_text(report.get("title")),
        document_number=_text(report.get("document_number")),
        case_number=_text(report.get("case_number")),
        introduction={
            "entrust_unit": _text(introduction.get("entrust_unit")),
            "entrust_persons": list(introduction.get("entrust_persons") or []),
            "entrust_time": _text(introduction.get("entrust_time")),
            "case_summary": _text(introduction.get("case_summary")),
            "inspection_requirement": _text(
                introduction.get("inspection_requirement")
            ),
            "inspection_place": _text(introduction.get("inspection_place")),
        },
    )
    case = CanonicalInspectionCase(
        case_info=case_info,
        inspection_period=CanonicalInspectionPeriod(
            time_range=_text(introduction.get("inspection_time_range"))
        ),
        materials=materials,
        inspectors=inspectors,
        software_tools=software_tools,
        inspection=CanonicalInspectionDetails(
            method=_text(inspection.get("method")),
            hardware_device=_text(inspection.get("hardware_device")),
            process_steps=list(inspection.get("process_steps") or []),
            result={
                "evidence_number": _text(result.get("evidence_number")),
                "data_summary": _text(result.get("data_summary")),
                "rar_filename": _text(result.get("rar_filename")),
                "md5_hash": _text(result.get("md5_hash")),
                "file_size": _text(result.get("file_size")),
            },
        ),
        attachments=dict(report.get("attachments") or {}),
    )
    return LegacyMigrationResult(
        canonical_case=case,
        missing_fields=(
            "field_provenance",
            "identifier_confidence",
            "inspector_snapshot_metadata",
            "archive_manifest",
            "template_profile",
            "plan_state",
        ),
        diagnostic_codes=("LEGACY_INPUT_INCOMPLETE",),
    )
