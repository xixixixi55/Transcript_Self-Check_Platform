"""Canonical inspection models at the report adapter boundary."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


MaterialKind = Literal["phone", "tablet", "unconfirmed"]
IdentifierType = Literal["imei1", "imei2", "serial_number"]
SoftwareCategory = Literal[
    "main_forensic", "winrar", "python_hashlib", "unclassified"
]
ConfirmationStatus = Literal["confirmed", "unconfirmed"]


class CanonicalBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FieldProvenance(CanonicalBaseModel):
    source_type: str
    source_file: str | None = None
    json_path: str | None = None
    adapter: str
    confidence: float | None = Field(default=None, ge=0, le=1)


class MaterialIdentifier(CanonicalBaseModel):
    type: IdentifierType
    value: str
    provenance: list[FieldProvenance] = Field(default_factory=list)


class Material(CanonicalBaseModel):
    id: str
    evidence_number: str
    type: MaterialKind = "unconfirmed"
    name: str = ""
    model: str = ""
    identifiers: list[MaterialIdentifier] = Field(default_factory=list)
    provenance: list[FieldProvenance] = Field(default_factory=list)


class InspectorSnapshot(CanonicalBaseModel):
    inspector_id: str | None = None
    name: str
    unit: str
    police_number: str
    selected_order: int = Field(ge=0)


class SoftwareTool(CanonicalBaseModel):
    category: SoftwareCategory
    name: str
    version: str
    display_name: str
    provenance: list[FieldProvenance] = Field(default_factory=list)
    confirmation_status: ConfirmationStatus = "unconfirmed"


class CanonicalCaseIntroduction(CanonicalBaseModel):
    entrust_unit: str = ""
    entrust_persons: list[str] = Field(default_factory=list)
    entrust_time: str = ""
    case_summary: str = ""
    inspection_requirement: str = ""
    inspection_place: str = ""


class CanonicalCaseInfo(CanonicalBaseModel):
    title: str
    document_number: str
    case_number: str = ""
    case_name: str = ""
    introduction: CanonicalCaseIntroduction = Field(
        default_factory=CanonicalCaseIntroduction
    )


class CanonicalInspectionPeriod(CanonicalBaseModel):
    created_at: str = ""
    reported_at: str = ""
    time_range: str = ""


class CanonicalInspectionResult(CanonicalBaseModel):
    evidence_number: str = ""
    data_summary: str = ""
    rar_filename: str = ""
    md5_hash: str = ""
    file_size: str = ""


class CanonicalInspectionDetails(CanonicalBaseModel):
    method: str = ""
    hardware_device: str = ""
    process_steps: list[dict[str, str | int]] = Field(default_factory=list)
    result: CanonicalInspectionResult = Field(
        default_factory=CanonicalInspectionResult
    )


class PhotoReference(CanonicalBaseModel):
    id: str
    provenance: list[FieldProvenance] = Field(default_factory=list)


class ArchiveManifestSummary(CanonicalBaseModel):
    manifest_id: str
    status: Literal["pending", "validated", "unavailable"]


class CanonicalAttachmentInputs(CanonicalBaseModel):
    extract_list: dict[str, object] = Field(default_factory=dict)
    photo_ids: list[str] = Field(default_factory=list)
    disc_number: str = ""
    burning_date: str | None = None


class CanonicalInspectionCase(CanonicalBaseModel):
    case_info: CanonicalCaseInfo
    inspection_period: CanonicalInspectionPeriod = Field(
        default_factory=CanonicalInspectionPeriod
    )
    materials: list[Material] = Field(default_factory=list)
    inspectors: list[InspectorSnapshot] = Field(default_factory=list)
    software_tools: list[SoftwareTool] = Field(default_factory=list)
    photos: list[PhotoReference] = Field(default_factory=list)
    archive_manifest: ArchiveManifestSummary | None = None
    provenance: list[FieldProvenance] = Field(default_factory=list)
    inspection: CanonicalInspectionDetails = Field(
        default_factory=CanonicalInspectionDetails
    )
    attachments: CanonicalAttachmentInputs = Field(
        default_factory=CanonicalAttachmentInputs
    )
