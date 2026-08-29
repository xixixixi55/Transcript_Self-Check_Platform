"""归档完成时的延迟光盘编号映射。

压缩可以在没有首个光盘编号（T003）时开始。压缩完成后，输入首个光盘编号会生成
完整序列，并按序号映射到计划分卷槽位；映射通过现有计划仓储持久化，从而推进
mapping_revision 和案件修订号。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..repository.archive.archive_plan_repository import ArchivePlanRepository
from ..repository.workbench_database import WorkbenchDatabase
from .disc_sequence_service import (
    archive_medium_for_mode, generate_disc_numbers, parse_archive_medium_sequence,
)


class DiscMappingError(ValueError):
    """不含路径的稳定光盘映射失败诊断。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class DiscMappingState:
    """案件计划是否存在，以及完整时的首个光盘编号。"""

    plan_exists: bool
    first_disc_number: str | None


def build_disc_mappings(
    first_disc_number: str, slots: list[Mapping[str, Any]],
    archive_mode: str = "standard_split",
) -> list[dict[str, Any]]:
    """按序号为 `slots` 生成序列。

    `slots` 必须已按序号排序并排除已移除槽位。
    """
    parsed = parse_archive_medium_sequence(first_disc_number, archive_mode)
    if not parsed.valid or parsed.sequence is None:
        medium_label = "硬盘" if archive_mode == "oversized_single_volume" else "首个光盘"
        raise DiscMappingError(
            parsed.error_code or "FIRST_DISC_NUMBER_INVALID", f"{medium_label}编号无效。",
        )
    if archive_mode == "oversized_single_volume" and len(slots) != 1:
        raise DiscMappingError("ARCHIVE_PLAN_INVALID", "硬盘归档必须对应一个完整压缩包。")
    numbers = generate_disc_numbers(first_disc_number, len(slots))
    disc_date = parsed.sequence.date
    return [
        {
            "slot_id": slot["slot_id"],
            "disc_number": numbers[index],
            "disc_date": disc_date,
            "source": "user",
            "confirmation": "confirmed",
        }
        for index, slot in enumerate(slots)
    ]


def active_slots(plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    """按序号排列的未移除分卷槽位。"""
    return sorted(
        (dict(slot) for slot in plan["volume_slots"] if slot["status"] != "removed"),
        key=lambda slot: slot["ordinal"],
    )


def first_mapped_disc_number(
    database: WorkbenchDatabase, case_id: str,
) -> str | None:
    """仅当每个活动槽位均有映射时返回首张光盘。"""
    return resolve_disc_mapping_state(database, case_id).first_disc_number


def resolve_disc_mapping_state(
    database: WorkbenchDatabase, case_id: str,
) -> DiscMappingState:
    """区分缺失计划与不完整的持久映射。"""
    plan = ArchivePlanRepository(database).get_latest_for_case(case_id)
    if plan is None:
        return DiscMappingState(plan_exists=False, first_disc_number=None)
    slots = active_slots(plan)
    if not slots:
        return DiscMappingState(plan_exists=True, first_disc_number=None)
    mappings = [slot.get("disc_mapping") for slot in slots]
    if not all(
        isinstance(mapping, Mapping)
        and mapping.get("confirmation") == "confirmed"
        for mapping in mappings
    ):
        return DiscMappingState(plan_exists=True, first_disc_number=None)
    numbers = [
        str(mapping.get("disc_number") or "").strip()
        for mapping in mappings if isinstance(mapping, Mapping)
    ]
    return DiscMappingState(
        plan_exists=True,
        first_disc_number=numbers[0] if all(numbers) else None,
    )


def apply_disc_mapping(
    database: WorkbenchDatabase,
    case_id: str,
    expected_revision: int,
    expected_plan_row_revision: int,
    first_disc_number: str,
    archive_mode: str = "standard_split",
) -> dict[str, Any]:
    """将 `first_disc_number` 的序列映射到最新案件计划。

    `expected_revision` 保护案件外壳（由调用方检查）；计划写入本身由计划记录自身的
    修订号通过 CAS 保护，因此两个独立计数器不会冲突。返回更新后的计划投影。
    """
    repository = ArchivePlanRepository(database)
    plan = repository.get_latest_for_case(case_id)
    if plan is None:
        raise DiscMappingError("ARCHIVE_PLAN_NOT_FOUND", "案件尚无归档计划。")
    slots = active_slots(plan)
    if not slots:
        raise DiscMappingError("ARCHIVE_PLAN_EMPTY", "归档计划没有可映射的分卷。")
    mappings = build_disc_mappings(first_disc_number, slots, archive_mode)
    updated = repository.update_mappings(
        plan["plan_id"], mappings, expected_plan_row_revision,
    )
    parts = [
        {
            "part_number": slot["ordinal"],
            "disc_number": slot["disc_mapping"]["disc_number"],
            "disc_date": slot["disc_mapping"]["disc_date"],
        }
        for slot in active_slots(updated)
        if slot.get("disc_mapping")
    ]
    return {
        "case_id": case_id,
        "task_id": "",
        "expected_revision": expected_revision,
        "plan_row_revision": updated["revision"],
        "lifecycle": "archive_verified",
        "archive_medium": archive_medium_for_mode(archive_mode),
        "prefix": parts[0]["disc_number"][:2] if parts else "",
        "disc_date": parts[0]["disc_date"] if parts else "",
        "parts": parts,
    }
