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
    PrimarySoftware,
    ProcessStep,
    SoftwareTool,
)
from .canonical_attachment_adapter_service import migrate_legacy_attachments
from .material_policy_service import material_from_legacy_item
from .software_policy_service import migrate_legacy_software

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
def _primary_software(case: CanonicalInspectionCase) -> PrimarySoftware | None:
    if case.primary_software is not None:
        return case.primary_software
    for tool in case.software_tools:
        if tool.category == "main_forensic":
            return PrimarySoftware(
                name=tool.name,
                version=tool.version,
                display_name=tool.display_name,
                confirmation_status=tool.confirmation_status,
                provenance=tool.provenance,
            )
    return None
def _software_tools(case: CanonicalInspectionCase) -> list[dict[str, str]]:
    primary = _primary_software(case)
    tools: list[dict[str, str]] = []
    if primary is not None and (primary.name or primary.version):
        tools.append({"name": primary.name, "version": primary.version})
    tools.extend(
        {"name": tool.name, "version": tool.version}
        for tool in case.software_tools
        if tool.category in {"winrar", "python_hashlib", "hashmyfiles"}
    )
    return tools

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
            "extractable": material.extractable if isinstance(material.extractable, bool) else bool(material.identifiers),
            "unextractable_reason": material.unextractable_reason,
            "evidence_number": material.evidence_number,
            "material_type": material.type,
            "material_type_status": material.classification.status,
            "material_type_source": material.classification.source,
            "material_type_diagnostic": material.classification.diagnostic_code,
        }
        for material in case.materials
    ]
    inspectors = [
        {
            "name": inspector.name,
            "unit": inspector.unit,
            "position": inspector.position,
            "badge_number": inspector.police_number,
        }
        for inspector in case.inspectors
    ]
    result = case.inspection.result
    primary_software = _primary_software(case)
    primary_software_name = primary_software.name if primary_software else ""
    primary_software_version = primary_software.version if primary_software else ""
    return {
        "title": case.case_info.title,
        "document_number": case.case_info.document_number,
        "case_number": case.case_info.case_number,
        "introduction": {
            "entrust_unit_prefix": intro.entrust_unit_prefix,
            "entrust_unit": intro.entrust_unit,
            "entrust_persons": list(intro.entrust_persons),
            "entrust_time": intro.entrust_time,
            "case_summary": intro.case_summary,
            "evidence_list": evidence_list,
            "inspection_requirement": intro.inspection_requirement,
            "inspection_time_range": case.inspection_period.time_range,
            "inspectors": inspectors,
            "inspector_snapshots": [
                {
                    "name": inspector.name,
                    "unit": inspector.unit,
                    "position": inspector.position,
                    "police_number": inspector.police_number,
                }
                for inspector in case.inspectors
            ],
            "inspection_place": intro.inspection_place,
        },
        "inspection": {
            "method": case.inspection.method,
            "hardware_device": case.inspection.hardware_device,
            "primary_software": (
                primary_software.model_dump() if primary_software else None
            ),
            "software_tools": _software_tools(case),
            "process_steps": [step.model_dump() for step in case.inspection.process_steps],
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
            "extract_list": case.attachments.extract_list.model_dump(),
            "photo_ids": list(case.attachments.photo_ids),
            "photo_groups": (
                [group.model_dump() for group in case.attachments.photo_groups]
                if case.attachments.photo_groups else None
            ),
            "disc_number": case.attachments.disc_number,
            "burning_date": case.attachments.burning_date,
            "disc_sequence": (
                case.attachments.disc_sequence.model_dump()
                if case.attachments.disc_sequence else None
            ),
        },
    }
def inspection_report_to_canonical(
    report: Mapping[str, Any],
) -> LegacyMigrationResult:
    """Best-effort legacy migration; it intentionally does not promise losslessness."""

    introduction = report.get("introduction") or {}
    inspection = report.get("inspection") or {}
    raw_evidence = introduction.get("evidence_list") or []
    materials = [
        material_from_legacy_item(item, index)
        for index, item in enumerate(raw_evidence)
        if isinstance(item, Mapping)
    ]

    raw_snapshots = introduction.get("inspector_snapshots")
    if isinstance(raw_snapshots, list):
        inspectors = [
            InspectorSnapshot(
                snapshot_id=_text(item.get("snapshot_id")) or None,
                name=_text(item.get("name")),
                unit=_text(item.get("unit")),
                position=_text(item.get("position")),
                police_number=_text(item.get("police_number")),
                selected_order=index,
            )
            for index, item in enumerate(raw_snapshots)
            if isinstance(item, Mapping)
        ]
    else:
        inspectors = [
        InspectorSnapshot(
            name=_text(item.get("name")),
            unit=_text(item.get("unit")),
            position=_text(item.get("position")),
            police_number=_text(item.get("badge_number")),
            selected_order=index,
        )
        for index, item in enumerate(introduction.get("inspectors") or [])
        if isinstance(item, Mapping)
        ]
    result = inspection.get("result") or {}
    primary_software, software_tools = migrate_legacy_software(inspection, result)
    case_info = CanonicalCaseInfo(
        title=_text(report.get("title")),
        document_number=_text(report.get("document_number")),
        case_number=_text(report.get("case_number")),
        introduction={
            "entrust_unit_prefix": _text(introduction.get("entrust_unit_prefix")),
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
        primary_software=primary_software,
        software_tools=software_tools,
        inspection=CanonicalInspectionDetails(
            method=_text(inspection.get("method")),
            hardware_device=_text(inspection.get("hardware_device")),
            process_steps=[
                ProcessStep(
                    step_number=int(step.get("step_number", idx + 1)),
                    content=_text(step.get("content")),
                )
                for idx, step in enumerate(inspection.get("process_steps") or [])
                if isinstance(step, Mapping)
            ],
            result={
                "evidence_number": _text(result.get("evidence_number")),
                "data_summary": _text(result.get("data_summary")),
                "rar_filename": _text(result.get("rar_filename")),
                "md5_hash": _text(result.get("md5_hash")),
                "file_size": _text(result.get("file_size")),
            },
        ),
        attachments=migrate_legacy_attachments(report),
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
