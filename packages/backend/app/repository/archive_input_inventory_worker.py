"""Parallel stat/open helpers for case-input inventory scanning."""

from __future__ import annotations

import os
from pathlib import Path


_DEFAULT_WORKERS = 4


def inventory_worker_count() -> int:
    """Parallel stat/open workers; reuses the copy-worker override."""
    raw = os.environ.get("BIJI_ARCHIVE_COPY_WORKERS")
    if raw is None:
        return _DEFAULT_WORKERS
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_WORKERS
    return max(value, 1)


def inspect_file(task: tuple[str, Path], check_readability: bool):
    """stat a single file and optionally probe readability (worker-safe)."""
    from .archive_input_repository import (
        ArchiveInputError,
        InputFileSnapshot,
        MAX_SAFE_INTEGER,
    )

    relative, path = task
    try:
        info = path.stat()
        if check_readability:
            open(path, "rb").close()
    except OSError as error:
        raise ArchiveInputError("ARCHIVE_PLAN_INVALID", "归档输入存在不可读文件。") from error
    if info.st_size < 0 or info.st_size > MAX_SAFE_INTEGER:
        raise ArchiveInputError("ARCHIVE_PLAN_INVALID", "归档输入文件大小无效。")
    return InputFileSnapshot(relative, path, info.st_size, info.st_mtime_ns)
