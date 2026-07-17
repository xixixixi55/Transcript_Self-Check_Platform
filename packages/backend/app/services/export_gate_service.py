"""Pure export eligibility checks for future pipeline integrations."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class ExportGateCode(str, Enum):
    WINRAR_UNAVAILABLE = "WINRAR_UNAVAILABLE"
    MATERIAL_TYPE_UNCONFIRMED = "MATERIAL_TYPE_UNCONFIRMED"
    PRIMARY_SOFTWARE_UNCONFIRMED = "PRIMARY_SOFTWARE_UNCONFIRMED"
    ODD_PHOTO_COUNT = "ODD_PHOTO_COUNT"
    ARCHIVE_MANIFEST_MISSING = "ARCHIVE_MANIFEST_MISSING"
    DISC_SEQUENCE_INVALID = "DISC_SEQUENCE_INVALID"


@dataclass(frozen=True)
class ExportGateIssue:
    code: ExportGateCode | str
    field: str
    message: str


@dataclass(frozen=True)
class ExportGateResult:
    allowed: bool
    blockers: tuple[ExportGateIssue, ...] = ()
    warnings: tuple[ExportGateIssue, ...] = ()


@dataclass(frozen=True)
class ExportGateInput:
    """Validated facts supplied by later services; no detection is performed here."""

    material_types_confirmed: bool = True
    primary_software_confirmed: bool = True
    photo_count_valid: bool = True
    disc_sequence_valid: bool = True
    automatic_archive_required: bool = False
    winrar_available: bool = True
    archive_manifest_required: bool = False
    archive_manifest_present: bool = True
    warnings: tuple[ExportGateIssue, ...] = field(default_factory=tuple)


def evaluate_export_gate(
    facts: ExportGateInput | None = None,
    *,
    warnings: Iterable[ExportGateIssue] = (),
) -> ExportGateResult:
    """Return stable blockers and warnings without filesystem side effects."""

    facts = facts or ExportGateInput()
    blockers: list[ExportGateIssue] = []
    if not facts.material_types_confirmed:
        blockers.append(
            ExportGateIssue(
                ExportGateCode.MATERIAL_TYPE_UNCONFIRMED,
                "materials",
                "所有检材类型必须先确认。",
            )
        )
    if not facts.primary_software_confirmed:
        blockers.append(
            ExportGateIssue(
                ExportGateCode.PRIMARY_SOFTWARE_UNCONFIRMED,
                "main_software",
                "主取证软件名称和版本必须先确认。",
            )
        )
    if not facts.photo_count_valid:
        blockers.append(
            ExportGateIssue(
                ExportGateCode.ODD_PHOTO_COUNT,
                "photos",
                "图片数量必须为零或正偶数。",
            )
        )
    if not facts.disc_sequence_valid:
        blockers.append(
            ExportGateIssue(
                ExportGateCode.DISC_SEQUENCE_INVALID,
                "disc_sequence",
                "光盘编号必须先通过格式和连续性校验。",
            )
        )
    if facts.automatic_archive_required and not facts.winrar_available:
        blockers.append(
            ExportGateIssue(
                ExportGateCode.WINRAR_UNAVAILABLE,
                "archive",
                "WinRAR 不可用，无法执行自动分卷。",
            )
        )
    if facts.archive_manifest_required and not facts.archive_manifest_present:
        blockers.append(
            ExportGateIssue(
                ExportGateCode.ARCHIVE_MANIFEST_MISSING,
                "archive_manifest",
                "缺少已验证的最终归档清单。",
            )
        )

    all_warnings = tuple(facts.warnings) + tuple(warnings)
    return ExportGateResult(
        allowed=not blockers,
        blockers=tuple(blockers),
        warnings=all_warnings,
    )
