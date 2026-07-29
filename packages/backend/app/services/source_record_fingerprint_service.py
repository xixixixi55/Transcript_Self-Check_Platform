"""Filesystem-only helpers for source metadata and fingerprint calculation."""

from __future__ import annotations

import hashlib
import os
import secrets
from pathlib import Path


class SourceFingerprintTransientError(OSError):
    """The source changed or was unavailable while its bytes were read."""


def directory_metadata(path: Path) -> dict[str, str | int | float | bool]:
    entries = [item for item in path.rglob("*") if not item.is_symlink()]
    return {"display_name": path.name, "file_count": sum(item.is_file() for item in entries), "directory_count": sum(item.is_dir() for item in entries), "modified_time_ns": int(path.stat().st_mtime_ns)}


def directory_summary(path: Path) -> dict[str, str | int | float | bool]:
    return {"display_name": path.name, "modified_time_ns": int(path.stat().st_mtime_ns)}


def validate_pending_locator(path: Path, allowed_root: Path) -> None:
    resolved_path = path.resolve(strict=True)
    resolved_root = allowed_root.resolve(strict=True)
    resolved_path.relative_to(resolved_root)
    if path.is_symlink() or not resolved_path.is_dir() or not os.access(resolved_path, os.R_OK):
        raise OSError("source unavailable")


def opaque_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(16)}"


def fingerprint(path: Path) -> str:
    if not path.is_dir() or path.is_symlink():
        raise SourceFingerprintTransientError("source unavailable")
    digest = hashlib.sha256()
    before = _snapshot(path)
    for relative, entry_type in before:
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(entry_type.encode("ascii"))
        digest.update(b"\0")
        if entry_type != "file":
            continue
        child = path.joinpath(*relative.split("/"))
        digest.update(_file_digest(child))
        digest.update(b"\0")
    after = _snapshot(path)
    if before != after:
        raise SourceFingerprintTransientError("source changed during fingerprint")
    return digest.hexdigest()


def _snapshot(path: Path) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []

    def visit(directory: Path, prefix: str) -> None:
        try:
            children = list(os.scandir(directory))
        except OSError as error:
            raise SourceFingerprintTransientError("source unavailable") from error
        for item in children:
            relative = f"{prefix}/{item.name}" if prefix else item.name
            normalized = _normalize_relative(relative)
            try:
                if item.is_symlink():
                    raise SourceFingerprintTransientError("source symlink changed")
                if item.is_dir(follow_symlinks=False):
                    entries.append((normalized, "directory"))
                    visit(Path(item.path), normalized)
                elif item.is_file(follow_symlinks=False):
                    entries.append((normalized, "file"))
                else:
                    raise SourceFingerprintTransientError("unsupported source entry")
            except OSError as error:
                if isinstance(error, SourceFingerprintTransientError):
                    raise
                raise SourceFingerprintTransientError("source unavailable") from error

    visit(path, "")
    return sorted(entries, key=lambda item: (item[0], item[1]))


def _file_digest(path: Path) -> bytes:
    first = _read_file_digest(path)
    second = _read_file_digest(path)
    if first != second:
        raise SourceFingerprintTransientError("source changed during fingerprint")
    return second


def _read_file_digest(path: Path) -> bytes:
    result = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            before = os.fstat(handle.fileno())
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                result.update(chunk)
            after = os.fstat(handle.fileno())
    except OSError as error:
        raise SourceFingerprintTransientError("source unavailable") from error
    if (
        before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or getattr(before, "st_ino", None) != getattr(after, "st_ino", None)
    ):
        raise SourceFingerprintTransientError("source changed during fingerprint")
    return result.digest()


def _normalize_relative(value: str) -> str:
    normalized = value.replace("\\", "/")
    return os.path.normcase(normalized).replace("\\", "/")
