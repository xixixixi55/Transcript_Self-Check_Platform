"""后端仓储共享的受限业务哈希算法元数据。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
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


def normalize_hash_digest(algorithm: str, value: object) -> str:
    normalized_algorithm = normalize_hash_algorithm(algorithm)
    digest = value.strip() if isinstance(value, str) else ""
    if (
        len(digest) != HASH_DIGEST_LENGTHS[normalized_algorithm]
        or any(char not in "0123456789abcdefABCDEF" for char in digest)
    ):
        raise ValueError("ARCHIVE_BUSINESS_HASH_INVALID")
    return digest.lower()


def normalize_manifest_part_hash(part: Mapping[str, Any]) -> tuple[str, str]:
    has_algorithm = "hash_algorithm" in part
    has_value = "hash_value" in part
    if has_algorithm or has_value:
        if not has_algorithm or not has_value:
            raise ValueError("ARCHIVE_BUSINESS_HASH_INVALID")
        algorithm = normalize_hash_algorithm(part.get("hash_algorithm"))
        return algorithm, normalize_hash_digest(algorithm, part.get("hash_value"))
    return "md5", normalize_hash_digest("md5", part.get("md5"))


def normalize_manifest_hashes(
    parts: Iterable[Mapping[str, Any]],
) -> tuple[str, tuple[str, ...]]:
    normalized = tuple(normalize_manifest_part_hash(part) for part in parts)
    if not normalized or len({algorithm for algorithm, _ in normalized}) != 1:
        raise ValueError("ARCHIVE_BUSINESS_HASH_INVALID")
    return normalized[0][0], tuple(digest for _, digest in normalized)


# 兼容现有调用方；新代码使用能够表明“规范 Manifest 哈希”的名称。
manifest_part_business_hash = normalize_manifest_part_hash
