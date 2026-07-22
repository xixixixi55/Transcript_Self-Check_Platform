"""Persistent ArchiveManifest registry independent from parsing cache files."""

from __future__ import annotations

import copy
import json
import math
import os
import re
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path


_INDEX_VERSION = 1
_INDEX_FILENAME = ".archive-manifest-index.json"
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_INDEX_LOCK = threading.RLock()


class ArchiveManifestRepositoryError(RuntimeError):
    """Safe registry diagnostics without local paths or report content."""


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


class ArchiveManifestRepository:
    """Keep archive metadata addressable while never deleting published parts."""

    def __init__(self, output_root: str | os.PathLike[str], clock=time.time) -> None:
        self.output_root = Path(output_root)
        self.compressed_root = self.output_root / "compressed"
        self.index_path = self.compressed_root / _INDEX_FILENAME
        self._clock = clock

    def save(
        self,
        *,
        source_key: str,
        input_fingerprint: str,
        archive_fingerprint: str,
        manifest_id: str,
        final_dir: str | os.PathLike[str],
        public_manifest: dict[str, object],
        created_at: float | None = None,
    ) -> PersistedArchiveManifest:
        relative = self._relative_final_dir(final_dir)
        now = float(self._clock())
        record = PersistedArchiveManifest(
            source_key, input_fingerprint, archive_fingerprint, manifest_id,
            relative, copy.deepcopy(public_manifest),
            float(created_at if created_at is not None else now), now,
        )
        with _INDEX_LOCK:
            records = self._read_records()
            for item in records:
                if (
                    item.source_key == source_key
                    and item.manifest_id != manifest_id
                    and (
                        item.input_fingerprint != input_fingerprint
                        or item.archive_fingerprint != archive_fingerprint
                    )
                    and item.status == "validated"
                ):
                    item.status = "stale"
            records = [item for item in records if item.manifest_id != manifest_id]
            records.append(record)
            self._write_records(records)
        return record

    def find_reusable(
        self, source_key: str, input_fingerprint: str, archive_fingerprint: str,
    ) -> list[PersistedArchiveManifest]:
        with _INDEX_LOCK:
            return [
                copy.deepcopy(item) for item in self._read_records()
                if item.status == "validated"
                and item.source_key == source_key
                and item.input_fingerprint == input_fingerprint
                and item.archive_fingerprint == archive_fingerprint
            ]

    def touch(self, manifest_id: str) -> None:
        with _INDEX_LOCK:
            records = self._read_records()
            changed = False
            for item in records:
                if item.manifest_id == manifest_id:
                    item.last_accessed_at = float(self._clock())
                    changed = True
                    break
            if changed:
                self._write_records(records)

    def mark_invalid(self, manifest_id: str) -> None:
        with _INDEX_LOCK:
            records = self._read_records()
            for item in records:
                if item.manifest_id == manifest_id and item.status == "validated":
                    item.status = "invalid"
                    self._write_records(records)
                    return

    def mark_source_changed(
        self,
        *,
        source_key: str,
        input_fingerprint: str,
        archive_fingerprint: str,
    ) -> None:
        """Retire older generations before a replacement archive is attempted."""
        with _INDEX_LOCK:
            records = self._read_records()
            changed = False
            for item in records:
                mismatch = item.input_fingerprint != input_fingerprint or item.archive_fingerprint != archive_fingerprint
                if item.status == "validated" and item.source_key == source_key and mismatch:
                    item.status = "stale"
                    changed = True
            if changed:
                self._write_records(records)

    def resolve_final_dir(self, record: PersistedArchiveManifest) -> Path:
        candidate = (self.compressed_root / Path(record.relative_final_dir)).resolve(strict=False)
        root = self.compressed_root.resolve(strict=False)
        try:
            candidate.relative_to(root)
        except ValueError as error:
            raise ArchiveManifestRepositoryError("归档登记目录无效。") from error
        return candidate
    def _relative_final_dir(self, final_dir: str | os.PathLike[str]) -> str:
        root = self.compressed_root.resolve(strict=False)
        candidate = Path(final_dir).resolve(strict=False)
        try:
            relative = candidate.relative_to(root)
        except ValueError as error:
            raise ArchiveManifestRepositoryError("归档登记目录无效。") from error
        value = relative.as_posix()
        if not value or value == "." or ".." in Path(value).parts:
            raise ArchiveManifestRepositoryError("归档登记目录无效。")
        return value
    def _read_records(self) -> list[PersistedArchiveManifest]:
        if not self.index_path.is_file():
            return []
        try:
            with self.index_path.open("r", encoding="utf-8") as stream:
                payload = json.load(stream)
        except (OSError, ValueError, TypeError):
            return []
        raw_records = payload.get("records") if isinstance(payload, dict) else None
        if not isinstance(raw_records, list):
            return []
        records = []
        for raw in raw_records:
            parsed = self._parse_record(raw)
            if parsed:
                records.append(parsed)
        return records

    @staticmethod
    def _parse_record(raw: object) -> PersistedArchiveManifest | None:
        if not isinstance(raw, dict):
            return None
        source_key = raw.get("source_key")
        input_fingerprint = raw.get("input_fingerprint")
        archive_fingerprint = raw.get("archive_fingerprint")
        manifest_id = raw.get("manifest_id")
        relative = raw.get("relative_final_dir")
        manifest = raw.get("public_manifest")
        created = raw.get("created_at")
        accessed = raw.get("last_accessed_at")
        status = raw.get("status", "validated")
        if (
            not all(isinstance(value, str) and _HASH_PATTERN.fullmatch(value)
                    for value in (source_key, input_fingerprint, archive_fingerprint))
            or not isinstance(manifest_id, str) or not manifest_id
            or not isinstance(relative, str) or not _safe_relative(relative)
            or not isinstance(manifest, dict)
            or not isinstance(created, (int, float)) or isinstance(created, bool)
            or not math.isfinite(float(created))
            or not isinstance(accessed, (int, float)) or isinstance(accessed, bool)
            or not math.isfinite(float(accessed))
            or status not in {"validated", "stale", "invalid"}
        ):
            return None
        return PersistedArchiveManifest(
            source_key, input_fingerprint, archive_fingerprint, manifest_id,
            relative, manifest, float(created), float(accessed), status,
        )

    def _write_records(self, records: list[PersistedArchiveManifest]) -> None:
        payload = {
            "version": _INDEX_VERSION,
            "records": [self._record_dict(item) for item in records],
        }
        temporary: Path | None = None
        try:
            self.compressed_root.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.compressed_root,
                prefix=".archive-manifest-", suffix=".tmp", delete=False,
            ) as stream:
                temporary = Path(stream.name)
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.index_path)
        except (OSError, TypeError, ValueError) as error:
            raise ArchiveManifestRepositoryError("归档登记无法保存。") from error
        finally:
            if temporary and temporary.exists():
                try:
                    temporary.unlink()
                except OSError:
                    pass

    @staticmethod
    def _record_dict(record: PersistedArchiveManifest) -> dict[str, object]:
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
        }


def _safe_relative(value: str) -> bool:
    normalized = value.replace("\\", "/")
    path = Path(normalized)
    return bool(normalized) and not path.is_absolute() and ".." not in path.parts
