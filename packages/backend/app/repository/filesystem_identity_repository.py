"""Stable, path-free identities for authorized local directories."""

from __future__ import annotations

import hashlib
import os
import stat
import threading
from pathlib import Path


class FilesystemIdentityError(ValueError):
    """Safe filesystem identity diagnostics without exposing local paths."""


_FILE_DIGEST_CACHE_LIMIT = 8192
_FILE_DIGEST_CACHE: dict[str, tuple[int, int, int, int, str]] = {}
_FILE_DIGEST_CACHE_LOCK = threading.RLock()


def resolve_directory(path: str | os.PathLike[str]) -> Path:
    """Resolve an existing directory and reject links or reparse points."""
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
    """Return a case-insensitive, separator-insensitive opaque directory key."""
    resolved = resolve_directory(path)
    normalized = os.path.normcase(os.path.normpath(os.fspath(resolved))).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def directory_content_fingerprint(path: str | os.PathLike[str]) -> str:
    """Hash relative entries and file bytes without storing their absolute path."""
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


def selected_files_content_fingerprint(
    root: str | os.PathLike[str], relative_files: list[str],
) -> str:
    """Hash a dynamically selected set of parser input files.

    The current request still checks every selected path and its metadata. The
    memo only skips rereading bytes when the same file identity and metadata
    are unchanged, so this never becomes a path-only cache.
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
    try:
        before = path.stat()
    except OSError as error:
        raise FilesystemIdentityError("Selected input file is unreadable.") from error
    normalized_path = os.path.normcase(
        os.path.normpath(os.fspath(path))
    ).casefold()
    key = hashlib.sha256(normalized_path.encode("utf-8")).hexdigest()
    metadata = (
        int(before.st_size), int(before.st_mtime_ns),
        int(getattr(before, "st_ctime_ns", 0)), int(getattr(before, "st_ino", 0)),
    )
    with _FILE_DIGEST_CACHE_LOCK:
        cached = _FILE_DIGEST_CACHE.get(key)
        if cached and cached[:4] == metadata:
            return cached[4]
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        after = path.stat()
    except OSError as error:
        raise FilesystemIdentityError("Selected input file is unreadable.") from error
    value = digest.hexdigest()
    after_metadata = (
        int(after.st_size), int(after.st_mtime_ns),
        int(getattr(after, "st_ctime_ns", 0)), int(getattr(after, "st_ino", 0)),
    )
    if metadata == after_metadata:
        with _FILE_DIGEST_CACHE_LOCK:
            if len(_FILE_DIGEST_CACHE) >= _FILE_DIGEST_CACHE_LIMIT:
                _FILE_DIGEST_CACHE.pop(next(iter(_FILE_DIGEST_CACHE)))
            _FILE_DIGEST_CACHE[key] = (*metadata, value)
    return value


def _is_unsafe_special_path(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        attributes = getattr(os.lstat(path), "st_file_attributes", 0)
        return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
    except OSError:
        return True
