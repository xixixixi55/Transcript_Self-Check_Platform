"""第 20 层报告子包：Parser 输入快照的安全文件系统原语。"""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

from .report_parse_input_models import DependencyRecord, ReportParseInputError


class ReportDependencyBudgetError(ReportParseInputError):
    """依赖文件超过调用方声明的读取上限。"""


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


def ancestor_identities(
    path: Path, source_root: Path,
) -> tuple[tuple[str, int, int], ...]:
    """记录来源根到候选父目录的稳定目录身份。"""
    try:
        parent = path.parent.relative_to(source_root)
        current = source_root
        result: list[tuple[str, int, int]] = []
        for part in (None, *parent.parts):
            if part is not None:
                current = current / part
            info = current.lstat()
            relative = "." if current == source_root else current.relative_to(source_root).as_posix()
            result.append((
                relative,
                int(getattr(info, "st_dev", 0)),
                int(getattr(info, "st_ino", 0)),
            ))
        return tuple(result)
    except (OSError, ValueError) as error:
        raise ReportParseInputError("报告依赖祖先路径无效。") from error


def require_ancestor_identities(
    source_root: Path,
    expected: tuple[tuple[str, int, int], ...],
) -> None:
    try:
        for relative, expected_device, expected_inode in expected:
            current = source_root if relative == "." else source_root / relative
            info = current.lstat()
            if (
                int(getattr(info, "st_dev", 0)) != expected_device
                or int(getattr(info, "st_ino", 0)) != expected_inode
            ):
                raise ReportParseInputError("报告依赖祖先目录在枚举后发生变化。")
    except OSError as error:
        raise ReportParseInputError("报告依赖祖先路径无效。") from error


def read_dependency(
    path: Path,
    dependency_root: Path,
    dependencies: dict[str, DependencyRecord],
) -> bytes:
    """稳定读取一个已选核心依赖，并记录相对路径和内容身份。"""
    require_regular_file(path)
    try:
        relative = path.relative_to(dependency_root).as_posix()
        before = path.stat()
        with path.open("rb") as stream:
            raw = stream.read()
        after = path.stat()
    except (OSError, ValueError) as error:
        raise ReportParseInputError("报告依赖文件无法读取。") from error
    if file_identity(before) != file_identity(after):
        raise ReportParseInputError("报告依赖文件在读取期间发生变化。")
    dependencies[relative.casefold()] = DependencyRecord(
        relative_path=relative,
        size_bytes=int(after.st_size),
        modified_time_ns=int(after.st_mtime_ns),
        stable_identity=stable_identity(after),
        content_digest=hashlib.sha256(raw).hexdigest(),
    )
    return raw


def read_bounded_dependency(
    path: Path,
    dependency_root: Path,
    max_bytes: int,
    *,
    expected_identity: tuple[int, int, int, int] | None = None,
    expected_ancestors: tuple[tuple[str, int, int], ...] | None = None,
) -> tuple[bytes, os.stat_result]:
    """绑定枚举身份并流式限量读取，拒绝路径、祖先或文件在读取期间变化。"""
    require_contained_path(path, dependency_root)
    if expected_ancestors is not None:
        require_ancestor_identities(dependency_root, expected_ancestors)
    require_regular_file(path)
    try:
        path_before = path.lstat()
        if path_before.st_size > max_bytes:
            raise ReportDependencyBudgetError("报告依赖文件超过读取上限。")
        if expected_identity is not None and file_identity(path_before) != expected_identity:
            raise ReportParseInputError("报告依赖文件在枚举后发生变化。")
        with path.open("rb") as stream:
            handle_before = os.fstat(stream.fileno())
            if not stat.S_ISREG(handle_before.st_mode):
                raise ReportParseInputError("报告依赖文件类型不受支持。")
            if file_identity(handle_before) != file_identity(path_before):
                raise ReportParseInputError("报告依赖文件在打开期间发生变化。")
            # 句柄打开后再次检查整条祖先链，避免目录在枚举与打开间被替换。
            require_contained_path(path, dependency_root)
            if expected_ancestors is not None:
                require_ancestor_identities(dependency_root, expected_ancestors)
            current = path.lstat()
            if file_identity(current) != file_identity(handle_before):
                raise ReportParseInputError("报告依赖路径在打开期间发生变化。")
            remaining = max_bytes
            chunks: list[bytes] = []
            while True:
                chunk = stream.read(min(64 * 1024, remaining + 1))
                if not chunk:
                    break
                if len(chunk) > remaining:
                    raise ReportDependencyBudgetError("报告依赖文件超过读取上限。")
                chunks.append(chunk)
                remaining -= len(chunk)
            handle_after = os.fstat(stream.fileno())
        if file_identity(handle_before) != file_identity(handle_after):
            raise ReportParseInputError("报告依赖文件在读取期间发生变化。")
        raw = b"".join(chunks)
        if len(raw) != int(handle_after.st_size):
            raise ReportParseInputError("报告依赖文件读取不完整。")
        require_contained_path(path, dependency_root)
        if expected_ancestors is not None:
            require_ancestor_identities(dependency_root, expected_ancestors)
        path_after = path.lstat()
        if file_identity(path_after) != file_identity(handle_after):
            raise ReportParseInputError("报告依赖路径在读取期间发生变化。")
        return raw, handle_after
    except (ReportParseInputError, ReportDependencyBudgetError):
        raise
    except OSError as error:
        raise ReportParseInputError("报告依赖文件无法读取。") from error


def fingerprint_dependencies(
    records: tuple[DependencyRecord, ...],
    adapter_id: str,
    adapter_version: str,
    structure_fingerprint: str,
) -> str:
    """把适配器语义与本次实际读取的核心依赖绑定。"""
    digest = hashlib.sha256()
    digest.update(adapter_id.encode("utf-8"))
    digest.update(b"\0" + adapter_version.encode("ascii"))
    digest.update(b"\0" + structure_fingerprint.encode("ascii") + b"\0")
    for record in records:
        digest.update(record.relative_path.casefold().encode("utf-8"))
        digest.update(f"\0{record.size_bytes}\0{record.modified_time_ns}\0".encode("ascii"))
        digest.update(record.stable_identity.encode("ascii"))
        digest.update(b"\0" + record.content_digest.encode("ascii") + b"\0")
    return digest.hexdigest()


def require_contained_path(path: Path, source_root: Path) -> None:
    """在读取前拒绝来源内部任何祖先链接或 Windows reparse point。"""
    try:
        relative = path.relative_to(source_root)
        current = source_root
        for part in (None, *relative.parts):
            if part is not None:
                current = current / part
            info = current.lstat()
            if current.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ReportParseInputError("报告目录包含不受支持的链接。")
        path.resolve(strict=True).relative_to(source_root.resolve(strict=True))
    except (OSError, ValueError) as error:
        raise ReportParseInputError("报告依赖路径无效。") from error


def require_directory(path: Path) -> None:
    if not path.is_dir() or path.is_symlink() or getattr(path.lstat(), "st_file_attributes", 0) & 0x400:
        raise ReportParseInputError("报告数据目录无效。")


def require_regular_file(path: Path) -> None:
    try:
        info = path.lstat()
    except OSError as error:
        raise ReportParseInputError("报告依赖文件无法读取。") from error
    if not stat.S_ISREG(info.st_mode) or path.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
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
    "ancestor_identities", "directory_entries", "file_entries", "file_identity",
    "fingerprint_dependencies", "read_bounded_dependency", "read_dependency",
    "ReportDependencyBudgetError", "reject_special",
    "require_ancestor_identities", "require_directory", "require_regular_file", "stable_identity",
    "require_contained_path",
]
