"""无路径 ArchiveManifest 索引的已验证序列化。"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
OPAQUE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,200}$")


@dataclass
class PersistedArchiveManifest:
    source_key: str
    input_fingerprint: str
    archive_fingerprint: str
    manifest_id: str
    relative_final_dir: str
    public_manifest: dict[str, object]
    created_at: float
    last_accessed_at: float
    status: str = "validated"
    workbench_attempt_id: str | None = None
    publication_id: str | None = None
    publication_digest: str | None = None


def parse_manifest_record(raw: object) -> PersistedArchiveManifest | None:
    if not isinstance(raw, dict):
        return None
    hashes = (
        raw.get("source_key"),
        raw.get("input_fingerprint"),
        raw.get("archive_fingerprint"),
    )
    manifest_id = raw.get("manifest_id")
    relative = raw.get("relative_final_dir")
    manifest = raw.get("public_manifest")
    created = raw.get("created_at")
    accessed = raw.get("last_accessed_at")
    status = raw.get("status", "validated")
    attempt_id = raw.get("workbench_attempt_id")
    publication_id = raw.get("publication_id")
    publication_digest = raw.get("publication_digest")
    if (
        not all(isinstance(value, str) and _HASH_PATTERN.fullmatch(value) for value in hashes)
        or not isinstance(manifest_id, str) or not manifest_id
        or not isinstance(relative, str) or not safe_relative(relative)
        or not isinstance(manifest, dict)
        or not _finite_number(created)
        or not _finite_number(accessed)
        or status not in {"validated", "stale", "invalid"}
        or (
            attempt_id is not None
            and (
                not isinstance(attempt_id, str)
                or not OPAQUE_ID_PATTERN.fullmatch(attempt_id)
            )
        )
        or (publication_id is not None and not isinstance(publication_id, str))
        or (publication_digest is not None and (
            not isinstance(publication_digest, str) or not _HASH_PATTERN.fullmatch(publication_digest)
        ))
    ):
        return None
    return PersistedArchiveManifest(
        *hashes, manifest_id, relative, manifest, float(created), float(accessed),
        status, attempt_id, publication_id, publication_digest,
    )


def manifest_record_dict(record: PersistedArchiveManifest) -> dict[str, object]:
    return {
        "source_key": record.source_key,
        "input_fingerprint": record.input_fingerprint,
        "archive_fingerprint": record.archive_fingerprint,
        "manifest_id": record.manifest_id,
        "relative_final_dir": record.relative_final_dir,
        "public_manifest": record.public_manifest,
        "created_at": record.created_at,
        "last_accessed_at": record.last_accessed_at,
        "status": record.status,
        "workbench_attempt_id": record.workbench_attempt_id,
        "publication_id": record.publication_id,
        "publication_digest": record.publication_digest,
    }


def safe_relative(value: str) -> bool:
    normalized = value.replace("\\", "/")
    path = Path(normalized)
    return bool(normalized) and not path.is_absolute() and ".." not in path.parts


def _finite_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )
