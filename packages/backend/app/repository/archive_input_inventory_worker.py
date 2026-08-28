"""用于案件输入清单扫描的并行 stat/open 辅助函数。"""

from __future__ import annotations

import os
from pathlib import Path


_DEFAULT_WORKERS = 4


def inventory_worker_count() -> int:
    """并行 stat/open 工作进程；复用复制工作进程覆盖项。"""
    raw = os.environ.get("BIJI_ARCHIVE_COPY_WORKERS")
    if raw is None:
        return _DEFAULT_WORKERS
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_WORKERS
    return max(value, 1)


def inspect_file(task: tuple[str, Path], check_readability: bool):
    """对单个文件执行 stat，并可选探测可读性（工作进程安全）。"""
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
