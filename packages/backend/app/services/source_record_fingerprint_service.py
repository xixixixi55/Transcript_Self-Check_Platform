"""Filesystem-only helpers for source metadata and fingerprint calculation."""

from __future__ import annotations

import hashlib
import os
import secrets
import stat
from collections.abc import Callable
from pathlib import Path


class SourceFingerprintTransientError(OSError):
    """The bounded source identity changed or became unavailable."""


class SourceFingerprintCancelledError(Exception):
    """The application is stopping and no source state should be changed."""


_CORE_REPORT_FILES = (
    "data_case_info.json",
    "data_device_lists.json",
    "data_report_info.json",
)
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


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
    """Bounded report identity: root/data/core-file metadata, no media walk.

    Full media inventory belongs to the background archive worker. Source review
    and archive-decision requests must stay independent of deep media-tree size.
    """
    return _fingerprint_entries(_stable_snapshot(path, should_cancel))


def fingerprint_with_metadata(
    path: Path, should_cancel: Callable[[], bool] | None = None,
) -> tuple[dict[str, str | int | float | bool], str]:
    """Derive public root metadata and a stable bounded source identity."""
    entries = _stable_snapshot(path, should_cancel)
    metadata = {
        "display_name": path.name,
        "modified_time_ns": int(path.stat().st_mtime_ns),
        "identity_entry_count": len(entries),
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
    data_dir = path / "data"
    targets: list[tuple[str, str, Path]] = [(".", "directory", path)]
    if data_dir.is_dir():
        targets.extend([
            ("data", "directory", data_dir),
            *[(f"data/{name}", "file", data_dir / name) for name in _CORE_REPORT_FILES],
        ])
    else:
        # Compatibility for non-production unit fixtures. Registered report
        # directories always pass the fixed `data`/core-file branch above.
        try:
            targets.extend(
                (item.name, "directory" if item.is_dir(follow_symlinks=False) else "file", Path(item.path))
                for item in os.scandir(path)
            )
        except OSError as error:
            raise SourceFingerprintTransientError("source unavailable") from error
    entries: list[tuple[str, str, int, int]] = []
    for relative, expected_type, target in targets:
        _raise_if_cancelled(should_cancel)
        try:
            info = os.lstat(target)
            if target.is_symlink() or bool(getattr(info, "st_file_attributes", 0) & _REPARSE_POINT):
                raise SourceFingerprintTransientError("source link changed")
            actual_type = "directory" if stat.S_ISDIR(info.st_mode) else "file" if stat.S_ISREG(info.st_mode) else "other"
            if actual_type != expected_type:
                raise SourceFingerprintTransientError("source structure changed")
            entries.append((
                _normalize_relative(relative), actual_type,
                int(info.st_size) if actual_type == "file" else 0,
                int(info.st_mtime_ns),
            ))
        except OSError as error:
            if isinstance(error, SourceFingerprintTransientError):
                raise
            raise SourceFingerprintTransientError("source unavailable") from error
    return entries


def _raise_if_cancelled(should_cancel: Callable[[], bool] | None) -> None:
    if should_cancel is not None and should_cancel():
        raise SourceFingerprintCancelledError("source verification cancelled")


def _normalize_relative(value: str) -> str:
    normalized = value.replace("\\", "/")
    return os.path.normcase(normalized).replace("\\", "/")
