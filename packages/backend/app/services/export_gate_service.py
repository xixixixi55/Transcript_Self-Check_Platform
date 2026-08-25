"""Pure export eligibility checks for future pipeline integrations."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class ExportGateCode(str, Enum):
    WINRAR_UNAVAILABLE = "WINRAR_UNAVAILABLE"
    ARCHIVE_INPUT_EMPTY = "ARCHIVE_INPUT_EMPTY"
    ARCHIVE_INPUT_CHANGED = "ARCHIVE_INPUT_CHANGED"
    ARCHIVE_TOO_LARGE = "ARCHIVE_TOO_LARGE"
    ARCHIVE_PLAN_INVALID = "ARCHIVE_PLAN_INVALID"
    ARCHIVE_EXECUTION_FAILED = "ARCHIVE_EXECUTION_FAILED"
    ARCHIVE_EXECUTION_TIMEOUT = "ARCHIVE_EXECUTION_TIMEOUT"
    ARCHIVE_INTEGRITY_TIMEOUT = "ARCHIVE_INTEGRITY_TIMEOUT"
    ARCHIVE_PARTS_INVALID = "ARCHIVE_PARTS_INVALID"
    ARCHIVE_MANIFEST_MISSING = "ARCHIVE_MANIFEST_MISSING"
    ARCHIVE_MANIFEST_INVALID = "ARCHIVE_MANIFEST_INVALID"
    ARCHIVE_MANIFEST_CONTEXT_MISMATCH = "ARCHIVE_MANIFEST_CONTEXT_MISMATCH"
    ARCHIVE_MANIFEST_PART_MISSING = "ARCHIVE_MANIFEST_PART_MISSING"
    ARCHIVE_MANIFEST_PART_CHANGED = "ARCHIVE_MANIFEST_PART_CHANGED"
    ARCHIVE_REPLAN_EXHAUSTED = "ARCHIVE_REPLAN_EXHAUSTED"
    ARCHIVE_INPUT_ROOT_NOT_ALLOWED = "ARCHIVE_INPUT_ROOT_NOT_ALLOWED"
    ARCHIVE_INPUT_PATH_INVALID = "ARCHIVE_INPUT_PATH_INVALID"
    ARCHIVE_INPUT_LINK_NOT_ALLOWED = "ARCHIVE_INPUT_LINK_NOT_ALLOWED"
    ARCHIVE_INPUT_OUTPUT_OVERLAP = "ARCHIVE_INPUT_OUTPUT_OVERLAP"
    ARCHIVE_CONTEXT_NOT_FOUND = "ARCHIVE_CONTEXT_NOT_FOUND"
    ARCHIVE_CONTEXT_EXPIRED = "ARCHIVE_CONTEXT_EXPIRED"
    ARCHIVE_CONTEXT_BUSY = "ARCHIVE_CONTEXT_BUSY"
    ARCHIVE_AUTHORIZATION_INVALID = "ARCHIVE_AUTHORIZATION_INVALID"
    ARCHIVE_AUTHORIZATION_EXPIRED = "ARCHIVE_AUTHORIZATION_EXPIRED"
    ARCHIVE_CONTEXT_INVALID = "ARCHIVE_CONTEXT_INVALID"
    ARCHIVE_EXECUTION_IN_PROGRESS = "ARCHIVE_EXECUTION_IN_PROGRESS"
    MATERIAL_TYPE_UNCONFIRMED = "MATERIAL_TYPE_UNCONFIRMED"
    PRIMARY_SOFTWARE_UNCONFIRMED = "PRIMARY_SOFTWARE_UNCONFIRMED"
    ATTACHMENT2_IMAGE_COUNT_ODD = "ATTACHMENT2_IMAGE_COUNT_ODD"
    ATTACHMENT2_MATERIAL_IMAGE_COUNT_INVALID = "ATTACHMENT2_MATERIAL_IMAGE_COUNT_INVALID"
    ATTACHMENT2_IMAGE_MAPPING_INVALID = "ATTACHMENT2_IMAGE_MAPPING_INVALID"
    ODD_PHOTO_COUNT = ATTACHMENT2_IMAGE_COUNT_ODD
    ATTACHMENT2_IMAGE_INVALID = "ATTACHMENT2_IMAGE_INVALID"
    ATTACHMENT_PLAN_INVALID = "ATTACHMENT_PLAN_INVALID"
    DISC_SEQUENCE_INVALID = "DISC_SEQUENCE_INVALID"
    FIRST_DISC_NUMBER_MISSING = "FIRST_DISC_NUMBER_MISSING"
    FIRST_DISC_NUMBER_INVALID = "FIRST_DISC_NUMBER_INVALID"
    FIRST_DISC_DATE_INVALID = "FIRST_DISC_DATE_INVALID"
    FIRST_DISC_SEQUENCE_INVALID = "FIRST_DISC_SEQUENCE_INVALID"
    TEMPLATE_PROFILE_MISMATCH = "TEMPLATE_PROFILE_MISMATCH"


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
    photo_mapping_valid: bool = True
    photo_mapping_error_code: str | None = None
    photo_assets_valid: bool = True
    photo_asset_error_code: str | None = None
    attachment_plan_valid: bool = True
    attachment_plan_error_code: str | None = None
    disc_sequence_valid: bool = True
    disc_sequence_error_code: str | None = None
    automatic_archive_required: bool = False
    winrar_available: bool = True
    archive_manifest_required: bool = False
    archive_manifest_present: bool = False
    archive_manifest_valid: bool = True
    archive_blocker_code: str | None = None
    material_type_fields: tuple[str, ...] = ()
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
        fields = facts.material_type_fields or ("materials",)
        blockers.extend(
            ExportGateIssue(
                ExportGateCode.MATERIAL_TYPE_UNCONFIRMED,
                field,
                "检材类型必须先确认手机或平板。",
            )
            for field in fields
        )
    if not facts.primary_software_confirmed:
        blockers.append(
            ExportGateIssue(
                ExportGateCode.PRIMARY_SOFTWARE_UNCONFIRMED,
                "inspection.primary_software",
                "主取证软件名称和版本必须先确认。",
            )
        )
    if not facts.photo_count_valid:
        blockers.append(
            ExportGateIssue(
                ExportGateCode.ATTACHMENT2_IMAGE_COUNT_ODD,
                "photos",
                "附件图片数量必须为偶数，请补充或删除一张图片后重新导出。",
            )
        )
    if not facts.photo_mapping_valid:
        blockers.append(
            ExportGateIssue(
                facts.photo_mapping_error_code or ExportGateCode.ATTACHMENT2_IMAGE_MAPPING_INVALID,
                "attachments.photo_groups",
                "附件2图片必须明确归属检材，且每个检材对应两张图片。",
            )
        )
    if not facts.photo_assets_valid:
        blockers.append(
            ExportGateIssue(
                facts.photo_asset_error_code or ExportGateCode.ATTACHMENT2_IMAGE_INVALID,
                "photos",
                "附件图片无法读取、解码或格式不受支持。",
            )
        )
    if not facts.attachment_plan_valid:
        blockers.append(
            ExportGateIssue(
                facts.attachment_plan_error_code or ExportGateCode.ATTACHMENT_PLAN_INVALID,
                "attachment_plan",
                "附件页面计划无效，请重新生成归档后重试。",
            )
        )
    if not facts.disc_sequence_valid:
        code = facts.disc_sequence_error_code or ExportGateCode.DISC_SEQUENCE_INVALID
        message = (
            "首个光盘编号不能为空。"
            if code == ExportGateCode.FIRST_DISC_NUMBER_MISSING
            else "首个光盘编号必须符合 GPyyyyMMdd-序号 或 GPyyyyMMddXX-序号格式（XX 为两位用户标识）并通过日期校验。"
        )
        blockers.append(
            ExportGateIssue(
                code,
                "attachments.disc_number",
                message,
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
    if facts.archive_blocker_code:
        blockers.append(
            ExportGateIssue(
                facts.archive_blocker_code,
                "archive",
                _archive_message(facts.archive_blocker_code),
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
    if facts.archive_manifest_required and facts.archive_manifest_present and not facts.archive_manifest_valid:
        blockers.append(
            ExportGateIssue(
                ExportGateCode.ARCHIVE_PARTS_INVALID,
                "archive_manifest",
                "归档清单与实际分卷不一致，请重新生成归档。",
            )
        )

    all_warnings = tuple(facts.warnings) + tuple(warnings)
    return ExportGateResult(
        allowed=not blockers,
        blockers=tuple(blockers),
        warnings=all_warnings,
    )


def _archive_message(code: str) -> str:
    messages = {
        "ARCHIVE_INPUT_EMPTY": "归档输入不能为空。",
        "ARCHIVE_INPUT_CHANGED": "归档输入在执行前已变化，请重新解析。",
        "ARCHIVE_TOO_LARGE": "归档输入超过当前归档策略允许的容量。",
        "ARCHIVE_PLAN_INVALID": "归档计划无效，请重新解析并检查案件名称。",
        "ARCHIVE_EXECUTION_FAILED": "WinRAR 归档执行失败，请检查后重试。",
        "ARCHIVE_EXECUTION_TIMEOUT": "归档执行超时，请确认系统资源充足后重试。",
        "ARCHIVE_INTEGRITY_TIMEOUT": "归档完整性校验超时，请确认系统资源充足后重试。",
        "ARCHIVE_PARTS_INVALID": "归档分卷校验失败，请重新生成归档。",
        "ARCHIVE_REPLAN_EXHAUSTED": "归档重规划次数已用尽，请检查输入文件。",
    }
    return messages.get(code, "归档门控未通过，请检查后重试。")
