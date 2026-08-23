"""Business hash selection and legacy-compatible projection helpers."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..repository.hash_algorithm_repository import (
    HASH_DIGEST_LENGTHS,
    HASH_DISPLAY_NAMES,
    manifest_part_business_hash,
    normalize_hash_algorithm,
)
from ..repository.archive_hash_repository import compute_hash_streaming


def report_hash_algorithm(report: Mapping[str, Any]) -> str:
    inspection = report.get("inspection")
    result = inspection.get("result") if isinstance(inspection, Mapping) else None
    raw = result.get("hash_algorithm") if isinstance(result, Mapping) else None
    try:
        return normalize_hash_algorithm(raw, legacy_default=True)
    except ValueError:
        return "md5"


def hash_display_name(algorithm: str) -> str:
    return HASH_DISPLAY_NAMES[normalize_hash_algorithm(algorithm)]


def hash_field_title(algorithm: str) -> str:
    return f"文件{hash_display_name(algorithm)}哈希值"


def hash_extraction_method(hardware: str, algorithm: str) -> str:
    device = hardware.strip() or "取证设备"
    return (
        f"使用{device}对检材进行检查，将检出数据生成报告，"
        f"然后对报告压缩并计算{hash_display_name(algorithm)}值"
    )


def archive_business_hash(
    path: Path, allowed_root: Path, algorithm: str, md5: str,
    verified_hashes: Mapping[str, str] | None,
) -> str:
    value = (
        md5 if algorithm == "md5"
        else verified_hashes.get(path.name)
        if verified_hashes is not None
        else compute_hash_streaming(path, allowed_root, algorithm)
    )
    expected_length = HASH_DIGEST_LENGTHS[algorithm]
    if (
        not isinstance(value, str)
        or len(value) != expected_length
        or any(char not in "0123456789abcdefABCDEF" for char in value)
    ):
        raise ValueError("ARCHIVE_PARTS_INVALID")
    return value


__all__ = [
    "hash_display_name",
    "archive_business_hash",
    "hash_extraction_method",
    "hash_field_title",
    "manifest_part_business_hash",
    "report_hash_algorithm",
]
