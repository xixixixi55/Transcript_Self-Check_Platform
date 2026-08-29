"""第 20 层报告子包：Parser 输入快照的安全文件系统原语。"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from .report_parse_input_models import ReportParseInputError


def directory_entries(root: Path) -> list[os.DirEntry[str]]:
    try:
        entries = list(os.scandir(root))
    except OSError as error:
        raise ReportParseInputError("报告目录无法读取。") from error
    result = []
    for entry in entries:
        if entry.is_dir(follow_symlinks=False):
            reject_special(entry)
            result.append(entry)
    return result


def file_entries(root: Path) -> list[os.DirEntry[str]]:
    try:
        entries = list(os.scandir(root))
    except OSError as error:
        raise ReportParseInputError("报告元数据目录无法读取。") from error
    result = []
    for entry in entries:
        if entry.is_file(follow_symlinks=False):
            reject_special(entry)
            result.append(entry)
    return result


def stable_identity(info: os.stat_result) -> str:
    return f"{int(getattr(info, 'st_dev', 0))}:{int(getattr(info, 'st_ino', 0))}"


def file_identity(info: os.stat_result) -> tuple[int, int, int, int]:
    return (
        int(info.st_size), int(info.st_mtime_ns),
        int(getattr(info, "st_dev", 0)), int(getattr(info, "st_ino", 0)),
    )


def require_directory(path: Path) -> None:
    if not path.is_dir() or path.is_symlink():
        raise ReportParseInputError("报告数据目录无效。")


def require_regular_file(path: Path) -> None:
    try:
        info = path.lstat()
    except OSError as error:
        raise ReportParseInputError("报告依赖文件无法读取。") from error
    if not stat.S_ISREG(info.st_mode) or path.is_symlink():
        raise ReportParseInputError("报告依赖文件类型不受支持。")


def reject_special(entry: os.DirEntry[str]) -> None:
    try:
        if entry.is_symlink() or bool(
            getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400
        ):
            raise ReportParseInputError("报告目录包含不受支持的链接。")
    except OSError as error:
        raise ReportParseInputError("报告目录无法读取。") from error


__all__ = [
    "directory_entries", "file_entries", "file_identity", "reject_special",
    "require_directory", "require_regular_file", "stable_identity",
]
