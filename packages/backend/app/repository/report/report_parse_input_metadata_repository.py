"""第 20 层：Parser 输入依赖的元数据优先验证。"""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from .report_parse_input_models import (
    CandidateDirectoryIndex,
    CandidateFileRecord,
    DependencyRecord,
    ReportParseInputError,
)
from .report_parse_input_filesystem import file_entries, stable_identity
from ..filesystem_identity_repository import resolve_directory
from .report_parse_input_selection_repository import is_device_metadata_name, is_json


@dataclass(frozen=True)
class CachedInputValidation:
    valid: bool
    dependencies: tuple[DependencyRecord, ...]
    candidate_indexes: tuple[CandidateDirectoryIndex, ...]


def validate_cached_input_metadata(
    data_root: str,
    dependencies: tuple[DependencyRecord, ...],
    candidate_indexes: tuple[CandidateDirectoryIndex, ...],
) -> CachedInputValidation:
    """先检查元数据，仅读取元数据发生变化的依赖。"""
    root = resolve_directory(data_root)
    current_indexes = tuple(
        _read_candidate_index(root, index) for index in candidate_indexes
    )
    if _candidate_membership_changed(candidate_indexes, current_indexes):
        return CachedInputValidation(False, (), current_indexes)

    updated: list[DependencyRecord] = []
    for dependency in dependencies:
        path = _safe_join(root, dependency.relative_path)
        current = _metadata(path, dependency.relative_path)
        if current is None:
            return CachedInputValidation(False, (), current_indexes)
        if _same_metadata(dependency, current):
            updated.append(dependency)
            continue
        if _content_digest(path) != dependency.content_digest:
            return CachedInputValidation(False, (), current_indexes)
        updated.append(DependencyRecord(
            dependency.relative_path,
            current.size_bytes,
            current.modified_time_ns,
            current.stable_identity,
            dependency.content_digest,
        ))
    updated.sort(key=lambda item: item.relative_path.casefold())
    return CachedInputValidation(True, tuple(updated), current_indexes)


def dependency_fingerprint(
    dependencies: tuple[DependencyRecord, ...],
) -> str:
    digest = hashlib.sha256()
    for record in sorted(dependencies, key=lambda item: item.relative_path.casefold()):
        digest.update(record.relative_path.casefold().encode("utf-8"))
        digest.update(f"\0{record.size_bytes}\0{record.modified_time_ns}\0".encode("ascii"))
        digest.update(record.stable_identity.encode("ascii"))
        digest.update(b"\0" + record.content_digest.encode("ascii") + b"\0")
    return digest.hexdigest()


def _read_candidate_index(
    root: Path, stored: CandidateDirectoryIndex,
) -> CandidateDirectoryIndex:
    directory = _safe_join(root, stored.relative_directory)
    if not directory.exists():
        return CandidateDirectoryIndex(stored.relative_directory, False, ())
    if not _safe_directory(directory):
        raise ReportParseInputError("报告候选目录类型不受支持。")
    files = [
        entry for entry in file_entries(directory)
        if is_json(entry.name) and is_device_metadata_name(entry.name)
    ]
    records = tuple(sorted(
        (_candidate_file_record(entry, root) for entry in files),
        key=lambda item: item.relative_path.casefold(),
    ))
    return CandidateDirectoryIndex(stored.relative_directory, True, records)


def _candidate_file_record(entry: os.DirEntry[str], root: Path) -> CandidateFileRecord:
    try:
        info = entry.stat(follow_symlinks=False)
        relative = Path(entry.path).relative_to(root).as_posix()
    except (OSError, ValueError) as error:
        raise ReportParseInputError("报告候选文件元数据无法读取。") from error
    return CandidateFileRecord(
        relative, int(info.st_size), int(info.st_mtime_ns), stable_identity(info),
    )


def _candidate_membership_changed(
    previous: tuple[CandidateDirectoryIndex, ...],
    current: tuple[CandidateDirectoryIndex, ...],
) -> bool:
    if len(previous) != len(current):
        return True
    for old, new in zip(previous, current):
        if old.relative_directory.casefold() != new.relative_directory.casefold():
            return True
        if old.exists != new.exists:
            return True
        old_paths = {item.relative_path.casefold() for item in old.files}
        new_paths = {item.relative_path.casefold() for item in new.files}
        if old_paths != new_paths:
            return True
    return False


def _metadata(path: Path, relative: str) -> DependencyRecord | None:
    try:
        info = path.lstat()
    except OSError:
        return None
    if not _safe_file_info(info):
        return None
    return DependencyRecord(
        relative, int(info.st_size), int(info.st_mtime_ns), stable_identity(info), "",
    )


def _same_metadata(old: DependencyRecord, current: DependencyRecord) -> bool:
    return (
        old.size_bytes == current.size_bytes
        and old.modified_time_ns == current.modified_time_ns
        and old.stable_identity == current.stable_identity
    )


def _content_digest(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        before = path.lstat()
        if not _safe_file_info(before):
            raise ReportParseInputError("报告依赖文件类型不受支持。")
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        after = path.lstat()
    except OSError as error:
        raise ReportParseInputError("报告依赖文件无法读取。") from error
    if (
        not _safe_file_info(after)
        or int(before.st_size) != int(after.st_size)
        or int(before.st_mtime_ns) != int(after.st_mtime_ns)
        or stable_identity(before) != stable_identity(after)
    ):
        raise ReportParseInputError("报告依赖文件在读取期间发生变化。")
    return digest.hexdigest()


def _safe_directory(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    return stat.S_ISDIR(info.st_mode) and not path.is_symlink() and not bool(
        getattr(info, "st_file_attributes", 0) & 0x400
    )


def _safe_file_info(info: os.stat_result) -> bool:
    return stat.S_ISREG(info.st_mode) and not bool(
        getattr(info, "st_file_attributes", 0) & 0x400
    )


def _safe_join(root: Path, relative: str) -> Path:
    posix = PurePosixPath(relative)
    windows = PureWindowsPath(relative)
    if (
        not relative or posix.is_absolute() or windows.is_absolute()
        or ".." in posix.parts or ".." in windows.parts
        or ":" in relative
    ):
        raise ReportParseInputError("缓存依赖路径无效。")
    return root.joinpath(*posix.parts)


__all__ = ["CachedInputValidation", "dependency_fingerprint", "validate_cached_input_metadata"]
