"""Pure binary-capacity archive planning rules."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from uuid import uuid4

from ..repository.archive_input_repository import MAX_SAFE_INTEGER
from .disc_sequence_service import generate_disc_numbers, parse_disc_sequence

BINARY_GB_BYTES = 1024 ** 3
STANDARD_VOLUME_MODE = "standard_volume"
OVERSIZED_SINGLE_MODE = "oversized_single"

@dataclass(frozen=True)
class ArchiveTier:
    gb: int
    volume_size_bytes: int
    max_part_count: int


@dataclass(frozen=True)
class ArchivePolicy:
    tiers: tuple[ArchiveTier, ...]
    max_replan_attempts: int = 2
    forced_tier_gb: int | None = None


PRODUCTION_ARCHIVE_POLICY = ArchivePolicy(
    tiers=(
        ArchiveTier(4, 4 * BINARY_GB_BYTES, 2),
        ArchiveTier(22, 22 * BINARY_GB_BYTES, 2),
        ArchiveTier(45, 45 * BINARY_GB_BYTES, 5),
    )
)


@dataclass(frozen=True)
class ArchiveSourceEntry:
    relative_path: str
    size_bytes: int
    modified_time_ns: int = 0


@dataclass(frozen=True)
class ArchiveDiagnostic:
    code: str
    message: str


@dataclass(frozen=True)
class ArchivePlan:
    plan_id: str
    case_display_name: str
    archive_base_name: str
    source_entries: tuple[ArchiveSourceEntry, ...]
    total_input_bytes: int
    volume_size_bytes: int | None
    volume_tier_gb: int | None
    expected_part_count: int
    max_part_count: int
    first_disc_number: str | None
    expected_disc_numbers: tuple[str, ...]
    max_replan_attempts: int
    status: str
    diagnostics: tuple[ArchiveDiagnostic, ...]
    archive_mode: str = STANDARD_VOLUME_MODE

    def public_dict(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "case_display_name": self.case_display_name,
            "archive_base_name": self.archive_base_name,
            "source_entries": [entry.__dict__ for entry in self.source_entries],
            "total_input_bytes": self.total_input_bytes,
            "archive_mode": self.archive_mode,
            "volume_size_bytes": self.volume_size_bytes,
            "volume_tier_gb": self.volume_tier_gb,
            "expected_part_count": self.expected_part_count,
            "max_part_count": self.max_part_count,
            "first_disc_number": self.first_disc_number,
            "expected_disc_numbers": list(self.expected_disc_numbers),
            "max_replan_attempts": self.max_replan_attempts,
            "status": self.status,
            "diagnostics": [item.__dict__ for item in self.diagnostics],
        }


_INVALID_NAME = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_RESERVED_NAMES = {
    "con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


def safe_archive_base_name(case_display_name: str) -> str:
    if not isinstance(case_display_name, str):
        return ""
    value = _INVALID_NAME.sub("_", case_display_name).strip(" .")
    if not value:
        return ""
    if value.casefold().split(".", 1)[0] in _RESERVED_NAMES:
        value = f"_{value}"
    return value


def _invalid_plan(
    case_name: str,
    base_name: str,
    entries: tuple[ArchiveSourceEntry, ...],
    policy: ArchivePolicy,
    diagnostics: list[ArchiveDiagnostic],
    *,
    total: int = 0,
) -> ArchivePlan:
    tier = policy.tiers[0] if policy.tiers else ArchiveTier(0, 0, 0)
    return ArchivePlan(
        plan_id=str(uuid4()), case_display_name=case_name, archive_base_name=base_name,
        source_entries=entries, total_input_bytes=total, volume_size_bytes=tier.volume_size_bytes,
        volume_tier_gb=tier.gb, expected_part_count=0, max_part_count=tier.max_part_count,
        first_disc_number=None, expected_disc_numbers=(),
        max_replan_attempts=policy.max_replan_attempts, status="blocked",
        diagnostics=tuple(diagnostics), archive_mode=STANDARD_VOLUME_MODE,
    )


def _normalize_entries(entries: list[ArchiveSourceEntry] | tuple[ArchiveSourceEntry, ...]) -> tuple[ArchiveSourceEntry, ...]:
    normalized: list[ArchiveSourceEntry] = []
    seen: set[str] = set()
    for item in entries:
        if not isinstance(item, ArchiveSourceEntry):
            raise ValueError("ARCHIVE_PLAN_INVALID")
        path = item.relative_path.replace("\\", "/")
        if not path or path.startswith("/") or ".." in path.split("/"):
            raise ValueError("ARCHIVE_PLAN_INVALID")
        if isinstance(item.size_bytes, bool) or not isinstance(item.size_bytes, int):
            raise ValueError("ARCHIVE_PLAN_INVALID")
        if item.size_bytes < 0 or item.size_bytes > MAX_SAFE_INTEGER:
            raise ValueError("ARCHIVE_PLAN_INVALID")
        key = path.casefold()
        if key in seen:
            raise ValueError("ARCHIVE_PLAN_INVALID")
        seen.add(key)
        normalized.append(ArchiveSourceEntry(path, item.size_bytes, item.modified_time_ns))
    return tuple(sorted(normalized, key=lambda item: item.relative_path.casefold()))


def _select_tier(total: int, policy: ArchivePolicy) -> ArchiveTier | None:
    if policy.forced_tier_gb is not None:
        return next((tier for tier in policy.tiers if tier.gb == policy.forced_tier_gb), None)
    for tier in policy.tiers:
        expected = math.ceil(total / tier.volume_size_bytes)
        if expected <= tier.max_part_count:
            return tier
    return None


def plan_archive(
    case_display_name: str,
    entries: list[ArchiveSourceEntry] | tuple[ArchiveSourceEntry, ...],
    *,
    first_disc_number: str | None = None,
    policy: ArchivePolicy = PRODUCTION_ARCHIVE_POLICY,
) -> ArchivePlan:
    """Build a plan only; this function never touches files or calls WinRAR."""

    case_name = case_display_name if isinstance(case_display_name, str) else ""
    base_name = safe_archive_base_name(case_name)
    try:
        normalized = _normalize_entries(entries)
    except ValueError as error:
        return _invalid_plan(case_name, base_name, (), policy, [ArchiveDiagnostic(str(error), "归档输入清单无效。")])
    if not policy.tiers or policy.max_replan_attempts < 0:
        return _invalid_plan(case_name, base_name, normalized, policy, [ArchiveDiagnostic("ARCHIVE_PLAN_INVALID", "归档策略无效。")])
    if not base_name:
        return _invalid_plan(case_name, base_name, normalized, policy, [ArchiveDiagnostic("ARCHIVE_PLAN_INVALID", "案件名称无法生成安全归档文件名。")])
    total = sum(item.size_bytes for item in normalized)
    if total > MAX_SAFE_INTEGER:
        return _invalid_plan(case_name, base_name, normalized, policy, [ArchiveDiagnostic("ARCHIVE_PLAN_INVALID", "归档输入总大小超出安全整数范围。")], total=total)
    if not normalized or total <= 0:
        return _invalid_plan(case_name, base_name, normalized, policy, [ArchiveDiagnostic("ARCHIVE_INPUT_EMPTY", "归档输入不能为空。")], total=total)

    diagnostics: list[ArchiveDiagnostic] = []
    if first_disc_number is not None:
        parsed = parse_disc_sequence(first_disc_number)
        if not parsed.valid:
            return _invalid_plan(case_name, base_name, normalized, policy, [ArchiveDiagnostic(parsed.error_code or "FIRST_DISC_NUMBER_INVALID", "首个光盘编号无效。")], total=total)

    tier = _select_tier(total, policy)
    if tier is None:
        if policy.forced_tier_gb is not None:
            diagnostics.append(ArchiveDiagnostic(
                "ARCHIVE_PLAN_INVALID", "指定的归档档位无效。",
            ))
            return _invalid_plan(
                case_name, base_name, normalized, policy, diagnostics, total=total,
            )
        diagnostics.append(ArchiveDiagnostic(
            "ARCHIVE_OVERSIZED_SINGLE_SELECTED",
            "输入超过标准分卷阈值，切换为超大单卷模式。",
        ))
        expected_discs = (
            tuple(generate_disc_numbers(first_disc_number, 1))
            if first_disc_number else ()
        )
        return ArchivePlan(
            plan_id=str(uuid4()), case_display_name=case_name,
            archive_base_name=base_name, source_entries=normalized,
            total_input_bytes=total, volume_size_bytes=None,
            volume_tier_gb=None, expected_part_count=1, max_part_count=1,
            first_disc_number=first_disc_number,
            expected_disc_numbers=expected_discs,
            max_replan_attempts=policy.max_replan_attempts, status="planned",
            diagnostics=tuple(diagnostics), archive_mode=OVERSIZED_SINGLE_MODE,
        )
    expected_count = math.ceil(total / tier.volume_size_bytes)
    if expected_count > tier.max_part_count:
        return _invalid_plan(case_name, base_name, normalized, policy, [ArchiveDiagnostic("ARCHIVE_TOO_LARGE", "归档输入超过当前档位允许卷数。")], total=total)
    diagnostics.append(ArchiveDiagnostic(
        "ARCHIVE_TIER_SELECTED", f"按二进制总大小选择 {tier.gb}GB 档位。",
    ))
    expected_discs = tuple(generate_disc_numbers(first_disc_number, expected_count)) if first_disc_number else ()
    return ArchivePlan(
        plan_id=str(uuid4()), case_display_name=case_name, archive_base_name=base_name,
        source_entries=normalized, total_input_bytes=total, volume_size_bytes=tier.volume_size_bytes,
        volume_tier_gb=tier.gb, expected_part_count=expected_count, max_part_count=tier.max_part_count,
        first_disc_number=first_disc_number, expected_disc_numbers=expected_discs,
        max_replan_attempts=policy.max_replan_attempts, status="planned",
        diagnostics=tuple(diagnostics), archive_mode=STANDARD_VOLUME_MODE,
    )


def replan_to_next_tier(plan: ArchivePlan, policy: ArchivePolicy) -> ArchivePlan | None:
    if plan.archive_mode != STANDARD_VOLUME_MODE or plan.volume_tier_gb is None:
        return None
    tiers = [tier.gb for tier in policy.tiers]
    try:
        next_gb = tiers[tiers.index(plan.volume_tier_gb) + 1]
    except (ValueError, IndexError):
        return None
    return plan_archive(
        plan.case_display_name, plan.source_entries,
        first_disc_number=plan.first_disc_number,
        policy=ArchivePolicy(policy.tiers, plan.max_replan_attempts, next_gb),
    )
