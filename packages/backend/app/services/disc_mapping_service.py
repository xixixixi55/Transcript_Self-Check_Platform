"""Deferred disc-number mapping for archive completion.

Compression may start without a first disc number (T003). Once compression is
done, entering the first disc number generates the full sequence and maps it
to the plan's volume slots in ordinal order; mapping is persisted through the
existing plan repository so the mapping_revision and case revision advance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..repository.archive_plan_repository import ArchivePlanRepository
from ..repository.workbench_database import WorkbenchDatabase
from .disc_sequence_service import generate_disc_numbers, parse_disc_sequence


class DiscMappingError(ValueError):
    """Stable, path-free diagnostic for disc mapping failures."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class DiscMappingState:
    """Whether a case plan exists and, if complete, its first disc number."""

    plan_exists: bool
    first_disc_number: str | None


def build_disc_mappings(
    first_disc_number: str, slots: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Generate the sequence for ``slots`` in ordinal order.

    ``slots`` must already be ordered by ordinal and exclude removed slots.
    """
    parsed = parse_disc_sequence(first_disc_number)
    if not parsed.valid or parsed.sequence is None:
        raise DiscMappingError(
            parsed.error_code or "FIRST_DISC_NUMBER_INVALID", "首个光盘编号无效。",
        )
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
    """Non-removed volume slots ordered by ordinal."""
    return sorted(
        (dict(slot) for slot in plan["volume_slots"] if slot["status"] != "removed"),
        key=lambda slot: slot["ordinal"],
    )


def first_mapped_disc_number(
    database: WorkbenchDatabase, case_id: str,
) -> str | None:
    """Return the first disc only when every active slot has a mapping."""
    return resolve_disc_mapping_state(database, case_id).first_disc_number


def resolve_disc_mapping_state(
    database: WorkbenchDatabase, case_id: str,
) -> DiscMappingState:
    """Distinguish an absent plan from an incomplete persisted mapping."""
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
) -> dict[str, Any]:
    """Map the sequence for ``first_disc_number`` onto the latest case plan.

    ``expected_revision`` guards the case shell (checked by the caller); the
    plan write itself is CAS-guarded by the plan row's own revision so the two
    independent counters never collide. Returns the updated plan projection.
    """
    repository = ArchivePlanRepository(database)
    plan = repository.get_latest_for_case(case_id)
    if plan is None:
        raise DiscMappingError("ARCHIVE_PLAN_NOT_FOUND", "案件尚无归档计划。")
    slots = active_slots(plan)
    if not slots:
        raise DiscMappingError("ARCHIVE_PLAN_EMPTY", "归档计划没有可映射的分卷。")
    mappings = build_disc_mappings(first_disc_number, slots)
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
        "prefix": parts[0]["disc_number"][:2] if parts else "",
        "disc_date": parts[0]["disc_date"] if parts else "",
        "parts": parts,
    }
