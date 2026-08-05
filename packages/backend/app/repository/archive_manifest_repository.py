"""Persistent ArchiveManifest registry independent from parsing cache files."""

from __future__ import annotations

import copy
import json
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path

from .archive_manifest_record_repository import (
    OPAQUE_ID_PATTERN,
    PersistedArchiveManifest,
    manifest_record_dict,
)
from .archive_manifest_index_repository import (
    ArchiveManifestIndexMixin, ArchiveManifestRepositoryError, _INDEX_FILENAME,
)
from .workbench_database import WorkbenchDatabase

_INDEX_VERSION = 1

class ArchiveManifestRepository(ArchiveManifestIndexMixin):
    """Keep archive metadata addressable until an explicit case deletion."""

    def __init__(
        self, output_root: str | os.PathLike[str], clock=time.time,
        database: WorkbenchDatabase | None = None,
    ) -> None:
        self.output_root = Path(output_root)
        self.compressed_root = self.output_root / "compressed"
        self.index_path = self.compressed_root / _INDEX_FILENAME
        self._clock = clock
        self.database = database

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
        publication_id: str | None = None,
        publication_digest: str | None = None,
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
            publication_id=publication_id, publication_digest=publication_digest,
        )
        with self._index_lock():
            records = self._read_records(bootstrap_relative=relative)
            for item in records:
                if item.manifest_id == manifest_id:
                    if item.status != "validated" or not _same_manifest_identity(item, record):
                        raise ArchiveManifestRepositoryError("归档 Manifest 身份冲突。")
                    if self.database is not None or not self.index_path.is_file():
                        self._write_records(records)
                    return copy.deepcopy(item)
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
        *, bootstrap_relative: str | None = None,
    ) -> list[PersistedArchiveManifest]:
        with self._index_lock():
            return [
                copy.deepcopy(item) for item in self._read_records(
                    bootstrap_relative=bootstrap_relative,
                )
                if item.status == "validated"
                and item.source_key == source_key
                and item.input_fingerprint == input_fingerprint
                and item.archive_fingerprint == archive_fingerprint
            ]

    def find_for_attempt(self, attempt_id: str) -> list[PersistedArchiveManifest]:
        if not OPAQUE_ID_PATTERN.fullmatch(attempt_id):
            return []
        with self._index_lock():
            return [
                copy.deepcopy(item) for item in self._read_records()
                if item.status == "validated"
                and item.workbench_attempt_id == attempt_id
            ]

    def find_by_manifest_id(self, manifest_id: str) -> list[PersistedArchiveManifest]:
        """Find validated records sharing an identity before any reuse/save operation."""
        with self._index_lock():
            return [
                copy.deepcopy(item) for item in self._read_records()
                if item.status == "validated" and item.manifest_id == manifest_id
            ]

    def touch(self, manifest_id: str) -> None:
        with self._index_lock():
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
        with self._index_lock():
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
        with self._index_lock():
            records = self._read_records()
            changed = False
            for item in records:
                mismatch = item.input_fingerprint != input_fingerprint or item.archive_fingerprint != archive_fingerprint
                if item.status == "validated" and item.source_key == source_key and mismatch:
                    item.status = "stale"
                    changed = True
            if changed:
                self._write_records(records)

    def remove_for_case(
        self, *, attempt_ids: set[str], relative_final_dirs: set[str],
    ) -> None:
        self.remove_records(
            attempt_ids=attempt_ids, relative_final_dirs=relative_final_dirs,
        )

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
            try:
                descriptor = os.open(str(self.compressed_root), os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            except OSError:
                pass
        except (OSError, TypeError, ValueError) as error:
            raise ArchiveManifestRepositoryError("归档登记无法保存。") from error
        finally:
            if temporary and temporary.exists():
                try:
                    temporary.unlink()
                except OSError:
                    pass


def _same_manifest_identity(
    existing: PersistedArchiveManifest, candidate: PersistedArchiveManifest,
) -> bool:
    return (
        existing.source_key == candidate.source_key
        and existing.input_fingerprint == candidate.input_fingerprint
        and existing.archive_fingerprint == candidate.archive_fingerprint
        and existing.relative_final_dir == candidate.relative_final_dir
        and existing.public_manifest == candidate.public_manifest
        and existing.workbench_attempt_id == candidate.workbench_attempt_id
        and existing.publication_id == candidate.publication_id
        and existing.publication_digest == candidate.publication_digest
    )


def _epoch(value: str) -> float:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError, OverflowError):
        return 0.0
