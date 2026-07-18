"""Streaming archive hashing with a constrained file root."""

from __future__ import annotations

import hashlib
from pathlib import Path


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def compute_md5_streaming(filepath: str | Path, allowed_root: str | Path) -> str:
    root = Path(allowed_root).resolve(strict=True)
    path = Path(filepath).resolve(strict=True)
    if not _within(path, root) or not path.is_file():
        raise ValueError("ARCHIVE_PARTS_INVALID")
    hasher = hashlib.md5()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
