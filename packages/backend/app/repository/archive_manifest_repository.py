"""Persistent ArchiveManifest registry independent from parsing cache files."""

from __future__ import annotations

import copy
import json
import os
import tempfile
import threading
import time
from pathlib import Path

from .archive_manifest_record_repository import (
    OPAQUE_ID_PATTERN,
    PersistedArchiveManifest,
    manifest_record_dict,
    parse_manifest_record,
)

_INDEX_VERSION = 1
_INDEX_FILENAME = ".archive-manifest-index.json"
_INDEX_LOCK = threading.RLock()


class ArchiveManifestRepositoryError(RuntimeError):
    """Safe registry diagnostics without local paths or report content."""


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
        workbench_attempt_id: str | None = None,
    ) -> PersistedArchiveManifest:
        if workbench_attempt_id is not None and not OPAQUE_ID_PATTERN.fullmatch(
            workbench_attempt_id
        ):
            raise ArchiveManifestRepositoryError("归档尝试标识无效。")
        relative = self._relative_final_dir(final_dir)
        now = float(self._clock())
        record = PersistedArchiveManifest(
            source_key, input_fingerprint, archive_fingerprint, manifest_id,
            relative, copy.deepcopy(public_manifest),
            float(created_at if created_at is not None else now), now,
            workbench_attempt_id=workbench_attempt_id,
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

    def find_for_attempt(self, attempt_id: str) -> list[PersistedArchiveManifest]:
        if not OPAQUE_ID_PATTERN.fullmatch(attempt_id):
            return []
        with _INDEX_LOCK:
            return [
                copy.deepcopy(item) for item in self._read_records()
                if item.status == "validated"
                and item.workbench_attempt_id == attempt_id
            ]

    def find_by_manifest_id(self, manifest_id: str) -> list[PersistedArchiveManifest]:
        """Find validated records sharing an identity before any reuse/save operation."""
        with _INDEX_LOCK:
            return [
                copy.deepcopy(item) for item in self._read_records()
                if item.status == "validated" and item.manifest_id == manifest_id
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
            parsed = parse_manifest_record(raw)
            if parsed:
                records.append(parsed)
        return records

    def _write_records(self, records: list[PersistedArchiveManifest]) -> None:
        payload = {
            "version": _INDEX_VERSION,
            "records": [manifest_record_dict(item) for item in records],
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
