"""验证真实 WinRAR 分卷输出并运行首卷完整性测试。"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from .winrar_discovery_repository import WinRarCapability
from .winrar_timeout_policy import compute_integrity_timeout


class ValidatorPlan(Protocol):
    archive_base_name: str
    volume_size_bytes: int | None
    max_part_count: int
    archive_mode: str


@dataclass(frozen=True)
class ValidatedArchivePart:
    part_number: int
    filename: str
    path: Path
    size_bytes: int


@dataclass(frozen=True)
class ArchiveValidationResult:
    valid: bool
    parts: tuple[ValidatedArchivePart, ...] = ()
    diagnostic_code: str | None = None
    safe_message: str = ""
    observed_part_count: int = 0
    replan_allowed: bool = False


IntegrityRunner = Callable[..., subprocess.CompletedProcess[str]]


def _invalid(
    code: str,
    message: str,
    *,
    observed_part_count: int = 0,
    replan_allowed: bool = False,
) -> ArchiveValidationResult:
    return ArchiveValidationResult(
        False, (), code, message, observed_part_count, replan_allowed,
    )


def validate_archive_parts(
    staging_dir: str | os.PathLike[str],
    plan: ValidatorPlan,
    capability: WinRarCapability,
    *,
    integrity_runner: IntegrityRunner = subprocess.run,
    timeout_seconds: int | None = None,
    integrity_started_callback: Callable[[], None] | None = None,
) -> ArchiveValidationResult:
    """仅接受编号连续且非空的 `.partN.rar` 输出。"""

    root = Path(staging_dir)
    if not root.is_dir():
        return _invalid("ARCHIVE_PARTS_INVALID", "归档临时产物目录无效。")
    archive_mode = getattr(plan, "archive_mode", "standard_split")
    if archive_mode not in {"standard_split", "oversized_single_volume"}:
        return _invalid("ARCHIVE_PARTS_INVALID", "归档模式无效。")
    pattern = re.compile(
        rf"^{re.escape(plan.archive_base_name)}\.part([1-9][0-9]*)\.rar$"
    )
    parts: dict[int, ValidatedArchivePart] = {}
    single: ValidatedArchivePart | None = None
    names_seen: set[str] = set()
    for entry in root.iterdir():
        if not entry.is_file():
            continue
        if re.search(r"\.r\d+$", entry.name, re.IGNORECASE):
            return _invalid("ARCHIVE_PARTS_INVALID", "归档不接受旧式分卷命名。")
        if entry.suffix.casefold() != ".rar":
            continue
        if entry.is_symlink():
            return _invalid("ARCHIVE_PARTS_INVALID", "归档分卷不能是链接文件。")
        name_key = entry.name.casefold()
        if name_key in names_seen:
            return _invalid("ARCHIVE_PARTS_INVALID", "归档分卷存在重复文件名。")
        names_seen.add(name_key)
        if entry.name == f"{plan.archive_base_name}.rar":
            if single is not None:
                return _invalid("ARCHIVE_PARTS_INVALID", "单卷归档文件重复。")
            size = entry.stat().st_size
            single = ValidatedArchivePart(1, entry.name, entry, size)
            continue
        match = pattern.fullmatch(entry.name)
        if not match:
            return _invalid("ARCHIVE_PARTS_INVALID", "归档分卷文件名不符合计划。")
        number = int(match.group(1))
        if number in parts:
            return _invalid("ARCHIVE_PARTS_INVALID", "归档分卷编号重复。")
        size = entry.stat().st_size
        if archive_mode == "oversized_single_volume":
            return _invalid("ARCHIVE_PARTS_INVALID", "超大单卷模式不接受分卷文件。")
        if (not isinstance(plan.volume_size_bytes, int)
                or size <= 0 or size > plan.volume_size_bytes):
            return _invalid("ARCHIVE_PARTS_INVALID", "归档分卷大小超出容量规则。")
        parts[number] = ValidatedArchivePart(number, entry.name, entry, size)

    if single is not None:
        if parts:
            return _invalid("ARCHIVE_PARTS_INVALID", "单卷和分卷归档不能同时存在。")
        if single.size_bytes <= 0:
            return _invalid("ARCHIVE_PARTS_INVALID", "归档分卷大小超出容量规则。")
        if (archive_mode == "standard_split"
                and (not isinstance(plan.volume_size_bytes, int)
                     or single.size_bytes > plan.volume_size_bytes)):
            return _invalid("ARCHIVE_PARTS_INVALID", "归档分卷大小超出容量规则。")
        parts[1] = single
    if 1 not in parts:
        return _invalid("ARCHIVE_PARTS_INVALID", "归档分卷缺少 part1。")
    if archive_mode == "oversized_single_volume" and (
        len(parts) != 1 or parts[1].filename != f"{plan.archive_base_name}.rar"
    ):
        return _invalid("ARCHIVE_PARTS_INVALID", "超大单卷归档产物无效。")
    if len(parts) > plan.max_part_count:
        return _invalid(
            "ARCHIVE_PARTS_INVALID", "归档实际分卷数超过当前档位限制。",
            observed_part_count=len(parts), replan_allowed=True,
        )
    numbers = sorted(parts)
    if numbers != list(range(1, len(numbers) + 1)):
        return _invalid("ARCHIVE_PARTS_INVALID", "归档分卷编号不连续。")
    if not capability.available or not capability.executable_path:
        return _invalid("WINRAR_UNAVAILABLE", "WinRAR 不可用，无法校验归档。")

    if integrity_started_callback is not None:
        integrity_started_callback()
    first = parts[1]
    total_archive_bytes = sum(p.size_bytes for p in parts.values())
    itimeout = (
        timeout_seconds
        if timeout_seconds is not None
        else compute_integrity_timeout(total_archive_bytes)
    )
    try:
        result = integrity_runner(
            [capability.executable_path, "t", "-inul", "-y", first.filename],
            cwd=str(root), capture_output=True, text=True,
            timeout=itimeout, shell=False,
        )
    except subprocess.TimeoutExpired:
        return _invalid("ARCHIVE_INTEGRITY_TIMEOUT", "归档完整性校验超时。")
    except (OSError, subprocess.SubprocessError):
        return _invalid("ARCHIVE_PARTS_INVALID", "WinRAR 完整性测试失败。")
    if result.returncode != 0:
        return _invalid("ARCHIVE_PARTS_INVALID", "WinRAR 完整性测试失败。")
    return ArchiveValidationResult(True, tuple(parts[number] for number in numbers))
