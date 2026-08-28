"""授权本地目录的稳定无路径标识。"""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path


class FilesystemIdentityError(ValueError):
    """不暴露本地路径的安全文件系统标识诊断。"""


def resolve_directory(path: str | os.PathLike[str]) -> Path:
    """解析现有目录并拒绝链接或重解析点。"""
    raw = os.fspath(path)
    candidate = Path(raw)
    raw_windows = raw.replace("/", "\\")
    if (
        not raw.strip()
        or "\x00" in raw
        or not candidate.is_absolute()
        or ".." in candidate.parts
        or raw_windows.startswith(("\\\\", "\\\\?\\", "\\\\.\\"))
        or not candidate.exists()
        or not candidate.is_dir()
    ):
        raise FilesystemIdentityError("输入目录无效。")
    current = candidate
    while True:
        if _is_unsafe_special_path(current):
            raise FilesystemIdentityError("输入目录包含不支持的链接或特殊路径。")
        parent = current.parent
        if parent == current:
            break
        current = parent
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise FilesystemIdentityError("输入目录无法访问。") from error
    if not resolved.is_dir() or resolved == Path(resolved.anchor):
        raise FilesystemIdentityError("输入目录无效。")
    return resolved


def normalized_directory_key(path: str | os.PathLike[str]) -> str:
    """返回不区分大小写和分隔符的不透明目录键。"""
    resolved = resolve_directory(path)
    normalized = os.path.normcase(os.path.normpath(os.fspath(resolved))).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def directory_content_fingerprint(path: str | os.PathLike[str]) -> str:
    """对相对条目和文件字节计算哈希，不存储绝对路径。"""
    root = resolve_directory(path)
    entries: list[tuple[str, str, Path]] = []
    pending = [root]
    while pending:
        current = pending.pop()
        try:
            children = list(os.scandir(current))
        except OSError as error:
            raise FilesystemIdentityError("输入目录无法读取。") from error
        for entry in children:
            item = Path(entry.path)
            if _is_unsafe_special_path(item):
                raise FilesystemIdentityError("输入目录包含不支持的链接或特殊路径。")
            relative = item.relative_to(root).as_posix()
            if entry.is_dir(follow_symlinks=False):
                entries.append(("directory", relative, item))
                pending.append(item)
            elif entry.is_file(follow_symlinks=False):
                entries.append(("file", relative, item))
    entries.sort(key=lambda value: (value[1].casefold(), value[0]))
    digest = hashlib.sha256()
    for kind, relative, item in entries:
        digest.update(kind.encode("utf-8"))
        digest.update(b"\0")
        digest.update(relative.replace("\\", "/").casefold().encode("utf-8"))
        digest.update(b"\0")
        if kind == "file":
            try:
                with item.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
            except OSError as error:
                raise FilesystemIdentityError("输入文件无法读取。") from error
        digest.update(b"\0")
    return digest.hexdigest()


def stable_directory_content_fingerprint(path: str | os.PathLike[str]) -> str:
    """使用稳定的来源目录采样围栏对字节和元数据计算哈希。"""
    root = resolve_directory(path)
    entries = _directory_entries(root)
    digest = hashlib.sha256()
    for kind, relative, item, size, modified_ns in entries:
        digest.update(kind.encode("utf-8"))
        digest.update(b"\0")
        digest.update(relative.replace("\\", "/").casefold().encode("utf-8"))
        digest.update(b"\0")
        if kind == "file":
            digest.update(_stable_file_digest(item))
        digest.update(f"{size}:{modified_ns}".encode("ascii"))
        digest.update(b"\0")
    if _directory_signature(entries) != _directory_signature(_directory_entries(root)):
        raise FilesystemIdentityError("输入目录在指纹采样期间发生变化。")
    return digest.hexdigest()


def directory_fingerprint_matches(path: str | os.PathLike[str], expected: str) -> bool:
    return stable_directory_content_fingerprint(path) == expected


def selected_files_content_fingerprint(
    root: str | os.PathLike[str], relative_files: list[str],
) -> str:
    """对动态选择的一组解析器输入文件计算哈希。

    每个请求都会读取选定字节。文件系统可能在快速同大小重写时保留大小和时间戳元数据，
    因此仅使用元数据的缓存可能错误复用过期的内容标识。
    """
    resolved_root = resolve_directory(root)
    entries: list[tuple[str, str, Path]] = []
    for raw_relative in sorted(set(relative_files), key=str.casefold):
        relative = Path(raw_relative)
        if relative.is_absolute() or ".." in relative.parts:
            raise FilesystemIdentityError("Selected input path is invalid.")
        item = resolved_root / relative
        current = item
        unsafe = False
        while True:
            unsafe = unsafe or _is_unsafe_special_path(current)
            if current == resolved_root:
                break
            current = current.parent
        if unsafe or not item.is_file():
            raise FilesystemIdentityError("Selected input file is unreadable.")
        entries.append(("file", relative.as_posix(), item))

    digest = hashlib.sha256()
    for kind, relative, item in entries:
        digest.update(kind.encode("utf-8"))
        digest.update(b"\0")
        digest.update(relative.replace("\\", "/").casefold().encode("utf-8"))
        digest.update(b"\0")
        digest.update(_file_content_digest(item).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _file_content_digest(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise FilesystemIdentityError("Selected input file is unreadable.") from error
    return digest.hexdigest()


def _directory_entries(root: Path) -> list[tuple[str, str, Path, int, int]]:
    entries: list[tuple[str, str, Path, int, int]] = []
    pending = [root]
    while pending:
        current = pending.pop()
        try:
            children = list(os.scandir(current))
        except OSError as error:
            raise FilesystemIdentityError("输入目录无法读取。") from error
        for entry in children:
            item = Path(entry.path)
            if _is_unsafe_special_path(item):
                raise FilesystemIdentityError("输入目录包含不支持的链接或特殊路径。")
            try:
                stat_result = entry.stat(follow_symlinks=False)
                relative = item.relative_to(root).as_posix()
                if entry.is_dir(follow_symlinks=False):
                    entries.append(("directory", relative, item, 0, stat_result.st_mtime_ns))
                    pending.append(item)
                elif entry.is_file(follow_symlinks=False):
                    entries.append(("file", relative, item, stat_result.st_size, stat_result.st_mtime_ns))
            except OSError as error:
                raise FilesystemIdentityError("输入目录无法读取。") from error
    return sorted(entries, key=lambda value: (value[1].casefold(), value[0]))


def _directory_signature(
    entries: list[tuple[str, str, Path, int, int]],
) -> list[tuple[str, str, int, int]]:
    return [(kind, relative, size, modified_ns) for kind, relative, _item, size, modified_ns in entries]


def _stable_file_digest(path: Path) -> bytes:
    first = _read_stable_file_digest(path)
    second = _read_stable_file_digest(path)
    if first != second:
        raise FilesystemIdentityError("输入文件在指纹采样期间发生变化。")
    return second


def _read_stable_file_digest(path: Path) -> bytes:
    result = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                result.update(chunk)
            after = os.fstat(stream.fileno())
    except OSError as error:
        raise FilesystemIdentityError("输入文件无法读取。") from error
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or getattr(before, "st_ino", None) != getattr(after, "st_ino", None)
    ):
        raise FilesystemIdentityError("输入文件在指纹采样期间发生变化。")
    return result.digest()


def _is_unsafe_special_path(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        attributes = getattr(os.lstat(path), "st_file_attributes", 0)
        return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
    except OSError:
        return True
