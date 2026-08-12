"""Canonical inspection models at the report adapter boundary."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


MaterialKind = Literal["phone", "tablet", "unconfirmed"]
MaterialClassificationStatus = Literal[
    "confirmed_by_report", "confirmed_by_user", "unconfirmed"
]
MaterialClassificationSource = Literal["report", "user", "none"]
IdentifierType = Literal["imei1", "imei2", "serial_number"]
SoftwareCategory = Literal[
    "main_forensic", "winrar", "python_hashlib", "hashmyfiles", "unclassified"
]
ConfirmationStatus = Literal[
    "confirmed_by_report", "confirmed_by_user", "unconfirmed", "confirmed"
]


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


class MaterialClassification(CanonicalBaseModel):
    status: MaterialClassificationStatus = "unconfirmed"
    source: MaterialClassificationSource = "none"
    rule_id: str | None = None
    diagnostic_code: str | None = None


class Material(CanonicalBaseModel):
    id: str
    evidence_number: str
    type: MaterialKind = "unconfirmed"
    name: str = ""
    model: str = ""
    extractable: bool | None = None
    identifiers: list[MaterialIdentifier] = Field(default_factory=list)
    provenance: list[FieldProvenance] = Field(default_factory=list)
    classification: MaterialClassification = Field(default_factory=MaterialClassification)


class InspectorSnapshot(CanonicalBaseModel):
    snapshot_id: str | None = None
    inspector_id: str | None = None
    name: str
    unit: str
    police_number: str
    selected_order: int | None = Field(default=None, ge=0)
    captured_at: str | None = None
    source_version: str | None = None


class SoftwareTool(CanonicalBaseModel):
    category: SoftwareCategory
    name: str
    version: str
    display_name: str
    provenance: list[FieldProvenance] = Field(default_factory=list)
    confirmation_status: ConfirmationStatus = "unconfirmed"


class PrimarySoftwareCandidate(CanonicalBaseModel):
    name: str
    version: str


class PrimarySoftware(CanonicalBaseModel):
    name: str = ""
    version: str = ""
    display_name: str = ""
    confirmation_status: ConfirmationStatus = "unconfirmed"
    provenance: list[FieldProvenance] = Field(default_factory=list)
    candidates: list[PrimarySoftwareCandidate] = Field(default_factory=list)


class CanonicalCaseIntroduction(CanonicalBaseModel):
    entrust_unit_prefix: str = ""
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


class ProcessStep(CanonicalBaseModel):
    step_number: int = Field(ge=1)
    content: str


class CanonicalInspectionDetails(CanonicalBaseModel):
    method: str = ""
    hardware_device: str = ""
    process_steps: list[ProcessStep] = Field(default_factory=list)
    result: CanonicalInspectionResult = Field(
        default_factory=CanonicalInspectionResult
    )


class PhotoReference(CanonicalBaseModel):
    id: str
    provenance: list[FieldProvenance] = Field(default_factory=list)


class ArchiveManifestSummary(CanonicalBaseModel):
    manifest_id: str
    status: Literal["pending", "validated", "unavailable"]


class MaterialPhotoGroup(CanonicalBaseModel):
    material_id: str
    material_number: str
    display_text: str
    ordered_image_ids: tuple[str, str]
    source_order: int = Field(ge=1)


class DiscSequence(CanonicalBaseModel):
    prefix: str
    date: str
    start_number: int = Field(ge=1)
    number_width: int = Field(ge=1)
    first_disc_number: str


class ExtractListColumn(CanonicalBaseModel):
    key: str
    title: str
    width: str | None = None


class ExtractListTable(CanonicalBaseModel):
    columns: list[ExtractListColumn] = Field(default_factory=list)
    rows: list[dict[str, str]] = Field(default_factory=list)


class CanonicalAttachmentInputs(CanonicalBaseModel):
    extract_list: ExtractListTable = Field(default_factory=ExtractListTable)
    photo_ids: list[str] = Field(default_factory=list)
    photo_groups: list[MaterialPhotoGroup] | None = None
    disc_number: str = ""
    burning_date: str | None = None
    disc_sequence: DiscSequence | None = None


class CanonicalInspectionCase(CanonicalBaseModel):
    case_info: CanonicalCaseInfo
    inspection_period: CanonicalInspectionPeriod = Field(
        default_factory=CanonicalInspectionPeriod
    )
    materials: list[Material] = Field(default_factory=list)
    inspectors: list[InspectorSnapshot] = Field(default_factory=list)
    primary_software: PrimarySoftware | None = None
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
