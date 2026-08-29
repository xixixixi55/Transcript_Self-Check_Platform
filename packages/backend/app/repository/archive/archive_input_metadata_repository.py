"""针对预览清单快照的快速纯元数据标识检查。"""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

from .archive_input_repository import (
    MAX_SAFE_INTEGER,
    ArchiveInputError,
    _is_unsafe_special_path,
    _validate_relative_path,
)


_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def metadata_fingerprint_for_directory(
    source_root: str | os.PathLike[str],
    output_root: str | os.PathLike[str] | None = None,
) -> str:
    """在不打开文件内容的情况下对当前路径、大小和 mtime 计算哈希。"""
    root = Path(source_root)
    if _is_unsafe_special_path(root):
        raise ArchiveInputError("ARCHIVE_INPUT_LINK_NOT_ALLOWED", "Archive input links are not allowed.")
    try:
        root = root.resolve(strict=True)
    except OSError as error:
        raise ArchiveInputError("ARCHIVE_INPUT_PATH_INVALID", "Archive input path is invalid.") from error
    if not root.is_dir():
        raise ArchiveInputError("ARCHIVE_INPUT_PATH_INVALID", "Archive input path is invalid.")
    current = root
    while True:
        if _is_unsafe_special_path(current):
            raise ArchiveInputError("ARCHIVE_INPUT_LINK_NOT_ALLOWED", "Archive input links are not allowed.")
        parent = current.parent
        if parent == current:
            break
        current = parent

    root_text = os.path.normcase(os.path.abspath(os.fspath(root)))
    output_text = None
    if output_root is not None:
        try:
            output_text = os.path.normcase(
                os.path.normpath(
                    str(Path(output_root).resolve(strict=False))
                )
            )
        except OSError as error:
            raise ArchiveInputError("ARCHIVE_INPUT_OUTPUT_OVERLAP", "Archive output path is invalid.") from error

    files: list[tuple[str, int, int]] = []
    directories: list[tuple[str, int]] = []
    pending = [root_text]
    while pending:
        current_text = pending.pop()
        try:
            entries = os.scandir(current_text)
        except OSError as error:
            raise ArchiveInputError("ARCHIVE_INPUT_PATH_INVALID", "Archive input path is invalid.") from error
        with entries:
            for entry in entries:
                if _unsafe_entry(entry):
                    raise ArchiveInputError("ARCHIVE_INPUT_LINK_NOT_ALLOWED", "Archive input links are not allowed.")
                path_text = os.path.normcase(os.path.abspath(entry.path))
                if entry.is_dir(follow_symlinks=False):
                    if output_text and _is_within(path_text, output_text):
                        continue
                    relative = os.path.relpath(path_text, root_text).replace(os.sep, "/")
                    _validate_relative_path(relative)
                    try:
                        info = entry.stat(follow_symlinks=False)
                    except OSError as error:
                        raise ArchiveInputError("ARCHIVE_INPUT_PATH_INVALID", "Archive input path is invalid.") from error
                    directories.append((relative, int(info.st_mtime_ns)))
                    pending.append(path_text)
                    continue
                if not entry.is_file(follow_symlinks=False):
                    continue
                if output_text and _is_within(path_text, output_text):
                    continue
                relative = os.path.relpath(path_text, root_text).replace(os.sep, "/")
                _validate_relative_path(relative)
                try:
                    info = entry.stat(follow_symlinks=False)
                except OSError as error:
                    raise ArchiveInputError("ARCHIVE_INPUT_PATH_INVALID", "Archive input path is invalid.") from error
                if info.st_size < 0 or info.st_size > MAX_SAFE_INTEGER:
                    raise ArchiveInputError("ARCHIVE_PLAN_INVALID", "Archive input size is invalid.")
                files.append((relative, int(info.st_size), int(info.st_mtime_ns)))
    return _metadata_fingerprint(files, directories)


def _unsafe_entry(entry: os.DirEntry[str]) -> bool:
    try:
        if entry.is_symlink():
            return True
        info = entry.stat(follow_symlinks=False)
        return bool(getattr(info, "st_file_attributes", 0) & _REPARSE_POINT)
    except OSError:
        return True


def _is_within(path: str, parent: str) -> bool:
    try:
        return os.path.commonpath((path, parent)) == parent
    except ValueError:
        return False


def _metadata_fingerprint(
    files: list[tuple[str, int, int]], directories: list[tuple[str, int]],
) -> str:
    digest = hashlib.sha256()
    for relative, modified_time_ns in sorted(directories, key=lambda item: item[0].casefold()):
        digest.update(b"directory\0")
        digest.update(relative.casefold().encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(modified_time_ns).encode("ascii"))
        digest.update(b"\0")
    for relative, size_bytes, modified_time_ns in sorted(files, key=lambda item: item[0].casefold()):
        digest.update(b"file\0")
        digest.update(relative.casefold().encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(size_bytes).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(modified_time_ns).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


__all__ = ["metadata_fingerprint_for_directory"]
