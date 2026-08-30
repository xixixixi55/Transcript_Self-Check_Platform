"""文件根目录受限的流式归档哈希计算。"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path
from typing import Any, BinaryIO

from ..integrity.hash_algorithm_repository import normalize_hash_algorithm


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def compute_md5_streaming(filepath: str | Path, allowed_root: str | Path) -> str:
    return compute_hash_streaming(filepath, allowed_root, "md5")


def compute_hash_streaming(
    filepath: str | Path, allowed_root: str | Path, algorithm: str, *,
    reader_factory: Callable[[Path], BinaryIO] | None = None,
    hasher_factory: Callable[[str], Any] = hashlib.new,
) -> str:
    root = Path(allowed_root).resolve(strict=True)
    path = Path(filepath).resolve(strict=True)
    if not _within(path, root) or not path.is_file():
        raise ValueError("ARCHIVE_PARTS_INVALID")
    try:
        normalized = normalize_hash_algorithm(algorithm)
    except ValueError as error:
        raise ValueError("ARCHIVE_HASH_ALGORITHM_INVALID") from error
    hasher = hasher_factory(normalized)
    open_reader = reader_factory or (lambda target: target.open("rb"))
    with open_reader(path) as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
