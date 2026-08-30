"""验证无路径 HashMyFiles 行投影。"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from .hash_algorithm_repository import normalize_hash_algorithm, normalize_hash_digest


class HashMyFilesRow(TypedDict):
    filename: str
    size_bytes: int
    hash_value: str


def validate_hashmyfiles_rows(
    rows: object, rar_paths: list[Path], hash_algorithm: str,
) -> list[HashMyFilesRow]:
    if not isinstance(rows, list):
        raise ValueError("rows missing")
    algorithm = normalize_hash_algorithm(hash_algorithm)
    expected = {path.name: path.stat().st_size for path in rar_paths}
    if len(expected) != len(rar_paths) or len(rows) != len(expected):
        raise ValueError("hash rows invalid")
    normalized: list[HashMyFilesRow] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("hash rows invalid")
        filename = row.get("filename")
        if not isinstance(filename, str) or filename in seen or filename not in expected:
            raise ValueError("hash rows invalid")
        try:
            size_bytes = int(str(row.get("size_bytes", "")).replace(",", "").replace("\u00a0", "").replace(" ", ""))
            digest = normalize_hash_digest(algorithm, row.get("hash_value"))
        except (TypeError, ValueError) as error:
            raise ValueError("hash rows invalid") from error
        if size_bytes != expected[filename]:
            raise ValueError("hash rows invalid")
        seen.add(filename)
        normalized.append({
            "filename": filename, "size_bytes": size_bytes, "hash_value": digest,
        })
    if seen != set(expected):
        raise ValueError("hash rows invalid")
    return normalized
