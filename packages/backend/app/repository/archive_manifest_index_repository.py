"""Durable, fail-closed index projection and cross-process writer lock."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from .archive_manifest_record_repository import (
    PersistedArchiveManifest, manifest_record_dict, parse_manifest_record,
)

_INDEX_VERSION = 1
_INDEX_FILENAME = ".archive-manifest-index.json"
_INDEX_LOCK = threading.RLock()


class ArchiveManifestRepositoryError(RuntimeError):
    """Safe registry diagnostics without local paths or report content."""


class ArchiveManifestIndexMixin:
    @contextmanager
    def _index_lock(self):
        """Coordinate writers across processes as well as threads."""
        with _INDEX_LOCK:
            self.compressed_root.mkdir(parents=True, exist_ok=True)
            lock_path = self.compressed_root / ".archive-manifest-index.lock"
            stream = lock_path.open("a+b")
            try:
                stream.seek(0, os.SEEK_END)
                if stream.tell() == 0:
                    stream.write(b"0")
                    stream.flush()
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
                yield
            finally:
                try:
                    if os.name == "nt":
                        import msvcrt
                        stream.seek(0)
                        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
                finally:
                    stream.close()

    def atomic_publish_generation(
        self, staging_dir: str | os.PathLike[str], final_dir: str | os.PathLike[str],
    ) -> None:
        """Move one sealed generation while app writers hold the shared lock."""
        staging = Path(staging_dir).resolve(strict=False)
        final = Path(final_dir).resolve(strict=False)
        root = self.compressed_root.resolve(strict=False)
        try:
            final.relative_to(root)
        except ValueError as error:
            raise ArchiveManifestRepositoryError("ARCHIVE_PUBLISH_TARGET_MISMATCH") from error
        if not staging.is_dir() or staging.is_symlink():
            raise ArchiveManifestRepositoryError("ARCHIVE_PUBLISH_STAGING_INVALID")
        with self._index_lock():
            if final.exists():
                raise ArchiveManifestRepositoryError("ARCHIVE_PUBLISH_TARGET_CONFLICT")
            try:
                os.rename(staging, final)
            except FileExistsError as error:
                raise ArchiveManifestRepositoryError("ARCHIVE_PUBLISH_TARGET_CONFLICT") from error
            except OSError as error:
                raise ArchiveManifestRepositoryError("ARCHIVE_PUBLISH_MOVE_FAILED") from error

    def remove_records(
        self, *, attempt_ids: set[str], relative_final_dirs: set[str],
    ) -> None:
        """Remove the index projection for an explicitly deleted case."""
        if not self.index_path.is_file():
            return
        with self._index_lock():
            records = self._read_index_records_for_mutation()
            retained = [
                item for item in records
                if item.workbench_attempt_id not in attempt_ids
                and item.relative_final_dir not in relative_final_dirs
            ]
            if len(retained) != len(records):
                self._write_records(retained)

    def _read_records(self, *, bootstrap_relative: str | None = None) -> list[PersistedArchiveManifest]:
        authoritative = self._authoritative_records()
        if not self.index_path.is_file():
            if authoritative:
                return authoritative
            if self._formal_assets_exist(exclude_relative=bootstrap_relative):
                raise ArchiveManifestRepositoryError("ARCHIVE_INDEX_MISSING")
            return []
        try:
            with self.index_path.open("r", encoding="utf-8") as stream:
                payload = json.load(stream)
        except (OSError, ValueError, TypeError):
            if authoritative:
                return authoritative
            raise ArchiveManifestRepositoryError("ARCHIVE_INDEX_CORRUPT")
        raw_records = payload.get("records") if isinstance(payload, dict) else None
        if not isinstance(raw_records, list):
            if authoritative:
                return authoritative
            raise ArchiveManifestRepositoryError("ARCHIVE_INDEX_CORRUPT")
        records: list[PersistedArchiveManifest] = []
        for raw in raw_records:
            parsed = parse_manifest_record(raw)
            if parsed is None:
                if authoritative:
                    return authoritative
                raise ArchiveManifestRepositoryError("ARCHIVE_INDEX_CORRUPT")
            records.append(parsed)
        if not records and self._formal_assets_exist(exclude_relative=bootstrap_relative):
            if authoritative:
                return authoritative
            raise ArchiveManifestRepositoryError("ARCHIVE_INDEX_UNTRUSTED")
        if self.database is not None:
            if not authoritative and records:
                raise ArchiveManifestRepositoryError("ARCHIVE_INDEX_UNTRUSTED")
            return authoritative
        return records

    def _read_index_records_for_mutation(self) -> list[PersistedArchiveManifest]:
        """Read the existing projection without requiring live DB authority."""
        try:
            with self.index_path.open("r", encoding="utf-8") as stream:
                payload = json.load(stream)
        except (OSError, ValueError, TypeError) as error:
            raise ArchiveManifestRepositoryError("ARCHIVE_INDEX_CORRUPT") from error
        raw_records = payload.get("records") if isinstance(payload, dict) else None
        if not isinstance(raw_records, list):
            raise ArchiveManifestRepositoryError("ARCHIVE_INDEX_CORRUPT")
        records: list[PersistedArchiveManifest] = []
        for raw in raw_records:
            parsed = parse_manifest_record(raw)
            if parsed is None:
                raise ArchiveManifestRepositoryError("ARCHIVE_INDEX_CORRUPT")
            records.append(parsed)
        return records

    def _authoritative_records(self) -> list[PersistedArchiveManifest]:
        if self.database is None:
            return []
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM archive_publish_intents WHERE deployment_instance_id=? "
                "AND phase IN ('published','indexed','verified') "
                "AND publication_status IN ('published','verified') "
                "ORDER BY created_at, intent_id",
                (self.database.deployment_instance_id,),
            ).fetchall()
        result: list[PersistedArchiveManifest] = []
        for row in rows:
            if not row["task_id"] or not row["publication_id"] or not row["publication_digest"]:
                raise ArchiveManifestRepositoryError("ARCHIVE_INDEX_AUTHORITY_INVALID")
            try:
                manifest = json.loads(row["public_manifest_json"])
            except (TypeError, ValueError) as error:
                raise ArchiveManifestRepositoryError("ARCHIVE_INDEX_AUTHORITY_INVALID") from error
            result.append(PersistedArchiveManifest(
                row["source_key"], row["input_fingerprint"], row["archive_fingerprint"],
                row["manifest_id"], row["relative_final_dir"], manifest,
                epoch(row["created_at"]), float(self._clock()), "validated",
                row["attempt_id"], row["publication_id"], row["publication_digest"],
            ))
        return result

    def _formal_assets_exist(self, *, exclude_relative: str | None = None) -> bool:
        if not self.compressed_root.is_dir():
            return False
        ignored = {_INDEX_FILENAME, ".archive-manifest-index.lock", ".staging", ".inputs"}
        excluded = (
            (self.compressed_root / exclude_relative).resolve(strict=False)
            if exclude_relative else None
        )
        for path in self.compressed_root.rglob("*"):
            relative = path.relative_to(self.compressed_root)
            if path.name in ignored or any(part in ignored for part in relative.parts):
                continue
            resolved = path.resolve(strict=False)
            if excluded is not None:
                try:
                    resolved.relative_to(excluded)
                    continue
                except ValueError:
                    pass
            if path.is_file():
                return True
        return False

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
            raise ArchiveManifestRepositoryError("ARCHIVE_INDEX_WRITE_FAILED") from error
        finally:
            if temporary and temporary.exists():
                try:
                    temporary.unlink()
                except OSError:
                    pass


def epoch(value: str) -> float:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError, OverflowError):
        return 0.0
