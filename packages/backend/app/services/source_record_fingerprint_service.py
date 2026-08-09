"""Filesystem-only helpers for source metadata and fingerprint calculation."""

from __future__ import annotations

import hashlib
import os
import secrets
from collections.abc import Callable
from pathlib import Path


class SourceFingerprintTransientError(OSError):
    """The source changed or was unavailable while its bytes were read."""


class SourceFingerprintCancelledError(Exception):
    """The application is stopping and no source state should be changed."""


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


def fingerprint(path: Path, should_cancel: Callable[[], bool] | None = None) -> str:
    """Metadata-only directory identity: path + type + size + mtime, no content reads.

    The full content hash lives in archive execution; request/revalidation paths
    must not read multi-gigabyte media. A same-size, timestamp-preserving in-place
    rewrite is intentionally outside this gate's guarantee.
    """
    return _fingerprint_entries(_stable_snapshot(path, should_cancel))


def fingerprint_with_metadata(
    path: Path, should_cancel: Callable[[], bool] | None = None,
) -> tuple[dict[str, str | int | float | bool], str]:
    """Derive initial metadata and identity from one stable two-pass snapshot."""
    entries = _stable_snapshot(path, should_cancel)
    metadata = {
        "display_name": path.name,
        "file_count": sum(entry_type == "file" for _, entry_type, _, _ in entries),
        "directory_count": sum(entry_type == "directory" for _, entry_type, _, _ in entries),
        "modified_time_ns": int(path.stat().st_mtime_ns),
    }
    return metadata, _fingerprint_entries(entries)


def _stable_snapshot(
    path: Path, should_cancel: Callable[[], bool] | None = None,
) -> list[tuple[str, str, int, int]]:
    _raise_if_cancelled(should_cancel)
    if not path.is_dir() or path.is_symlink():
        raise SourceFingerprintTransientError("source unavailable")
    before = _snapshot(path, should_cancel)
    after = _snapshot(path, should_cancel)
    if before != after:
        raise SourceFingerprintTransientError("source changed during fingerprint")
    return before


def _fingerprint_entries(entries: list[tuple[str, str, int, int]]) -> str:
    digest = hashlib.sha256()
    for relative, entry_type, size_bytes, modified_ns in entries:
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(entry_type.encode("ascii"))
        digest.update(b"\0")
        digest.update(f"{size_bytes}:{modified_ns}".encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _snapshot(
    path: Path, should_cancel: Callable[[], bool] | None = None,
) -> list[tuple[str, str, int, int]]:
    entries: list[tuple[str, str, int, int]] = []

    def visit(directory: Path, prefix: str) -> None:
        _raise_if_cancelled(should_cancel)
        try:
            children = list(os.scandir(directory))
        except OSError as error:
            raise SourceFingerprintTransientError("source unavailable") from error
        for item in children:
            _raise_if_cancelled(should_cancel)
            relative = f"{prefix}/{item.name}" if prefix else item.name
            normalized = _normalize_relative(relative)
            try:
                if item.is_symlink():
                    raise SourceFingerprintTransientError("source symlink changed")
                if item.is_dir(follow_symlinks=False):
                    visit(Path(item.path), normalized)
                    entries.append((normalized, "directory", 0, int(os.stat(item.path, follow_symlinks=False).st_mtime_ns)))
                elif item.is_file(follow_symlinks=False):
                    info = os.stat(item.path, follow_symlinks=False)
                    entries.append((normalized, "file", int(info.st_size), int(info.st_mtime_ns)))
                else:
                    raise SourceFingerprintTransientError("unsupported source entry")
            except OSError as error:
                if isinstance(error, SourceFingerprintTransientError):
                    raise
                raise SourceFingerprintTransientError("source unavailable") from error

    visit(path, "")
    return sorted(entries, key=lambda item: (item[0], item[1]))


def _raise_if_cancelled(should_cancel: Callable[[], bool] | None) -> None:
    if should_cancel is not None and should_cancel():
        raise SourceFingerprintCancelledError("source verification cancelled")


def _normalize_relative(value: str) -> str:
    normalized = value.replace("\\", "/")
    return os.path.normcase(normalized).replace("\\", "/")
