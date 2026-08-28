"""第 20 层：Parser 缓存条目的已验证内存模型。"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .report_parse_input_models import CandidateDirectoryIndex, DependencyRecord
from .report_parsing_cache_manifest_repository import parse_manifest


_KEY_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ReportCacheEntry:
    cache_key: str
    cache_version: int
    source_fingerprint: str
    last_accessed_at: float
    result: dict[str, object]
    dependencies: tuple[DependencyRecord, ...] | None = None
    candidate_indexes: tuple[CandidateDirectoryIndex, ...] | None = None


def parse_cache_entry(
    payload: object, cache_key: str, cache_version: int,
) -> ReportCacheEntry | None:
    if not isinstance(payload, dict):
        return None
    version = payload.get("cache_version")
    source_fingerprint = payload.get("source_fingerprint")
    last_accessed_at = payload.get("last_accessed_at")
    result = payload.get("result")
    dependencies, candidate_indexes = parse_manifest(payload)
    if ("dependencies" in payload or "candidate_indexes" in payload) and (
        dependencies is None or candidate_indexes is None
    ):
        return None
    if (
        payload.get("cache_key") != cache_key
        or version != cache_version
        or not isinstance(version, int)
        or isinstance(version, bool)
        or not isinstance(source_fingerprint, str)
        or not _KEY_PATTERN.fullmatch(source_fingerprint)
        or not isinstance(last_accessed_at, (int, float))
        or isinstance(last_accessed_at, bool)
        or not math.isfinite(float(last_accessed_at))
        or not isinstance(result, dict)
        or not result.get("report")
    ):
        return None
    return ReportCacheEntry(
        cache_key, version, source_fingerprint, float(last_accessed_at), result,
        dependencies, candidate_indexes,
    )


__all__ = ["ReportCacheEntry", "parse_cache_entry"]
