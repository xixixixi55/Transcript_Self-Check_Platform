"""Output-size and filesystem-object safety checks for archive manifests."""

from __future__ import annotations

import os
import stat
from pathlib import Path

_DISC_CAPACITY_TIERS = (4_000_000_000, 22_000_000_000, 45_000_000_000)


def compute_disc_capacity(size_bytes: int) -> int:
    if not isinstance(size_bytes, int) or isinstance(size_bytes, bool):
        raise ValueError("disc_capacity: size_bytes must be an integer")
    if size_bytes <= 0:
        raise ValueError("disc_capacity: size_bytes must be positive")
    for tier in _DISC_CAPACITY_TIERS:
        if size_bytes <= tier:
            return tier
    raise ValueError("disc_capacity: size_bytes exceeds maximum disc capacity")


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
