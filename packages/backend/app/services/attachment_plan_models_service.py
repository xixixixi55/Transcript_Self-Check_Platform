"""Immutable models emitted by the pure attachment planning service."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AttachmentPartRow:
    part_id: str
    part_number: int
    filename: str
    md5: str


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


@dataclass(frozen=True)
class Attachment2State:
    photo_count: int
    renderer: str = "legacy-compatible"


@dataclass(frozen=True)
class Attachment3PagePlan:
    page_number: int
    show_attachment_title: bool
    part_id: str
    part_number: int
    filename: str
    md5: str
    disc_number: str
    burning_date: str


@dataclass(frozen=True)
class AttachmentPlan:
    profile_id: str
    archive_manifest_id: str
    attachment_summary: AttachmentSummaryPlan
    attachment1_pages: tuple[Attachment1PagePlan, ...]
    attachment2_state: Attachment2State
    attachment3_pages: tuple[Attachment3PagePlan, ...]
    diagnostics: tuple[str, ...]
    status: str
