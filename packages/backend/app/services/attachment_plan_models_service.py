"""Immutable models emitted by the pure attachment planning service."""

from __future__ import annotations

from dataclasses import dataclass


ARCHIVE_ROWS_PAGE_KIND = "archive_rows"
INSPECTOR_FINAL_PAGE_KIND = "inspector_final"


@dataclass(frozen=True)
class AttachmentPartRow:
    part_id: str
    part_number: int
    filename: str
    size_bytes: int
    md5: str
    disc_capacity_bytes: int
    volume_size_bytes: int


@dataclass(frozen=True)
class AttachmentSummaryPlan:
    inspection_date: str
    archive_part_count: int
    disc_numbers: tuple[str, ...]


@dataclass(frozen=True)
class Attachment1PagePlan:
    page_number: int
    page_kind: str
    show_attachment_title: bool
    serial_rows: tuple[AttachmentPartRow, ...]
    source_text: str
    extraction_method: str
    signature_blank_row_count: int


@dataclass(frozen=True)
class Attachment2State:
    photo_count: int
    renderer: str = "legacy-compatible"


@dataclass(frozen=True)
class Attachment2ImagePlan:
    source_image_id: str
    sequence_number: int
    safe_display_name: str
    slot: str
    evidence_number: str


@dataclass(frozen=True)
class MaterialPhotoGroup:
    material_id: str
    material_number: str
    display_text: str
    images: tuple[Attachment2ImagePlan, Attachment2ImagePlan]
    source_order: int


@dataclass(frozen=True)
class Attachment2PagePlan:
    page_number: int
    show_attachment_title: bool
    layout: str
    images: tuple[Attachment2ImagePlan, ...]
    material_groups: tuple[MaterialPhotoGroup, ...]
    inspection_result_material_numbers: tuple[str, ...]

    @property
    def evidence_numbers(self) -> tuple[str, ...]:
        """Compatibility accessor for the page's planned material numbers."""
        return self.inspection_result_material_numbers

    @property
    def top_image(self) -> Attachment2ImagePlan:
        """Compatibility accessor for the first image in the planned page."""
        return self.images[0]

    @property
    def bottom_image(self) -> Attachment2ImagePlan:
        """Compatibility accessor for the second image in the planned page."""
        return self.images[1]


@dataclass(frozen=True)
class Attachment3PagePlan:
    page_number: int
    show_attachment_title: bool
    part_id: str
    part_number: int
    filename: str
    size_bytes: int
    md5: str
    disc_capacity_bytes: int
    disc_number: str
    burning_date: str
    volume_size_bytes: int


@dataclass(frozen=True)
class AttachmentPlan:
    profile_id: str
    archive_manifest_id: str
    attachment_summary: AttachmentSummaryPlan
    attachment1_pages: tuple[Attachment1PagePlan, ...]
    attachment2_state: Attachment2State
    attachment2_pages: tuple[Attachment2PagePlan, ...]
    attachment3_pages: tuple[Attachment3PagePlan, ...]
    diagnostics: tuple[str, ...]
    status: str
