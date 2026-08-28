"""归档 Manifest 的输出大小和文件系统对象安全检查。"""

from __future__ import annotations

import os
import stat
from pathlib import Path

_DISC_CAPACITY_TIERS = (4 * 1024**3, 22 * 1024**3, 45 * 1024**3)
_LEGACY_DISC_CAPACITY_TIERS = (4_000_000_000, 22_000_000_000, 45_000_000_000)


def compute_disc_capacity(size_bytes: int) -> int:
    if not isinstance(size_bytes, int) or isinstance(size_bytes, bool):
        raise ValueError("disc_capacity: size_bytes must be an integer")
    if size_bytes <= 0:
        raise ValueError("disc_capacity: size_bytes must be positive")
    for tier in _DISC_CAPACITY_TIERS:
        if size_bytes <= tier:
            return tier
    raise ValueError("disc_capacity: size_bytes exceeds maximum disc capacity")


def compute_manifest_disc_capacity(
    size_bytes: int, archive_mode: object,
) -> int | None:
    """使用 Manifest 的持久化单位契约返回容量。"""

    if archive_mode == "oversized_single_volume":
        return None
    if archive_mode in {None, "legacy_standard_split"}:
        if not isinstance(size_bytes, int) or isinstance(size_bytes, bool):
            raise ValueError("disc_capacity: size_bytes must be an integer")
        if size_bytes <= 0:
            raise ValueError("disc_capacity: size_bytes must be positive")
        for tier in _LEGACY_DISC_CAPACITY_TIERS:
            if size_bytes <= tier:
                return tier
        raise ValueError("disc_capacity: size_bytes exceeds legacy maximum")
    if archive_mode == "standard_split":
        return compute_disc_capacity(size_bytes)
    raise ValueError("archive mode is invalid")


def is_safe_output_file(path: Path) -> bool:
    try:
        return (
            path.is_file() and not path.is_symlink()
            and not bool(
                getattr(os.lstat(path), "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            )
        )
    except OSError:
        return False


def assert_safe_output_file(path: Path) -> None:
    if not is_safe_output_file(path):
        raise OSError("unsafe archive output")
