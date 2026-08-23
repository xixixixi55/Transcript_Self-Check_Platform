"""Validate path-free HashMyFiles row projections."""

from __future__ import annotations

from pathlib import Path


def validate_hashmyfiles_rows(
    rows: object, rar_paths: list[Path], digest_length: int,
) -> None:
    if not isinstance(rows, list):
        raise ValueError("rows missing")
    expected = sorted((path.name, path.stat().st_size) for path in rar_paths)
    actual = sorted((
        str(row["filename"]),
        int(str(row["size_bytes"]).replace(",", "").replace("\u00a0", "").replace(" ", "")),
    ) for row in rows if isinstance(row, dict))
    valid_hash = len(rows) == len(rar_paths) and all(
        isinstance(row, dict)
        and len(str(row.get("hash_value", ""))) == digest_length
        and all(
            char in "0123456789abcdefABCDEF"
            for char in str(row.get("hash_value", ""))
        )
        for row in rows
    )
    if actual != expected or not valid_hash:
        raise ValueError("hash rows invalid")
