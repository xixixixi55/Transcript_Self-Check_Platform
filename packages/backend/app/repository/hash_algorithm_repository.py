"""后端仓储共享的受限业务哈希算法元数据。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

HASH_ALGORITHMS = frozenset({"md5", "sha1", "sha256"})
HASH_DIGEST_LENGTHS = {"md5": 32, "sha1": 40, "sha256": 64}
HASH_DISPLAY_NAMES = {"md5": "MD5", "sha1": "SHA-1", "sha256": "SHA-256"}


def normalize_hash_algorithm(value: object, *, legacy_default: bool = False) -> str:
    if value is None and legacy_default:
        return "md5"
    if not isinstance(value, str):
        raise ValueError("INVALID_HASH_ALGORITHM")
    normalized = value.strip().lower().replace("-", "")
    if normalized not in HASH_ALGORITHMS:
        raise ValueError("INVALID_HASH_ALGORITHM")
    return normalized


def manifest_part_business_hash(part: Mapping[str, Any]) -> tuple[str, str]:
    algorithm = normalize_hash_algorithm(part.get("hash_algorithm"), legacy_default=True)
    value = part.get("hash_value")
    if value is None and algorithm == "md5":
        value = part.get("md5")
    digest = str(value or "").strip()
    if (
        len(digest) != HASH_DIGEST_LENGTHS[algorithm]
        or any(char not in "0123456789abcdefABCDEF" for char in digest)
    ):
        raise ValueError("ARCHIVE_BUSINESS_HASH_INVALID")
    return algorithm, digest
