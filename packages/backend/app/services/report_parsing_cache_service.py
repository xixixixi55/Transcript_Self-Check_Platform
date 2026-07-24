"""LRU orchestration for persistent report parsing results."""

from __future__ import annotations

import hashlib
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
import weakref

from ..config import REPORT_PARSING_CACHE_LIMIT
from ..repository.filesystem_identity_repository import (
    directory_content_fingerprint,
    normalized_directory_key,
)
from ..repository.report_parsing_cache_repository import (
    ReportCacheEntry,
    ReportParsingCacheError,
    ReportParsingCacheRepository,
)
from ..repository.report_parse_input_metadata_repository import (
    dependency_fingerprint,
    validate_cached_input_metadata,
)
from ..repository.report_parse_input_models import ReportParseInputError, ReportParseInputSnapshot


class ReportParsingCacheService:
    """Coordinate cache reads, builds and cleanup without touching archive roots."""

    def __init__(
        self,
        *,
        max_entries: int = REPORT_PARSING_CACHE_LIMIT,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.max_entries = max_entries
        self._clock = clock
        self._lock = threading.RLock()
        self._key_locks: weakref.WeakValueDictionary[str, threading.Lock] = weakref.WeakValueDictionary()
        self._stores: dict[str, ReportParsingCacheRepository] = {}
        self._inflight: dict[str, int] = {}
        self._generation = 0

    def load_or_build(
        self,
        source_dir: str,
        cache_dir: str,
        cache_version: int,
        builder: Callable[[], dict[str, object]],
        *,
        fingerprint_dir: str | None = None,
        fingerprint: Callable[[str], str] = directory_content_fingerprint,
        snapshot_builder: Callable[[], ReportParseInputSnapshot] | None = None,
        generation_token: int | None = None,
    ) -> dict[str, object]:
        # Capture the cache generation before any potentially slow fingerprint
        # work. A clear that starts after this request must invalidate its
        # eventual write, even if fingerprinting has not reached the key lock.
        with self._lock:
            generation = self._generation if generation_token is None else generation_token
        cache_key = normalized_directory_key(source_dir)
        source_fingerprint = None
        if snapshot_builder is None:
            source_fingerprint = fingerprint(fingerprint_dir or source_dir)
        store_key = self._store_key(cache_dir)
        operation_key = f"{store_key}\0{cache_key}\0{generation}"
        with self._key_lock(operation_key):
            store = self._store(cache_dir)
            entry = store.load(cache_key, cache_version)
            if snapshot_builder is None:
                if entry and entry.source_fingerprint == source_fingerprint:
                    touched = store.touch(cache_key, cache_version)
                    if touched:
                        store.prune(
                            cache_version,
                            max_entries=self.max_entries,
                            protected_keys=self._protected_keys(store_key),
                        )
                        return touched.result
            else:
                if entry and entry.dependencies is not None and entry.candidate_indexes is not None:
                    try:
                        validation = validate_cached_input_metadata(
                            fingerprint_dir or source_dir,
                            entry.dependencies,
                            entry.candidate_indexes,
                        )
                    except ReportParseInputError:
                        store.remove(cache_key)
                        raise
                    if validation.valid:
                        updated_fingerprint = dependency_fingerprint(validation.dependencies)
                        touched = store.touch(
                            cache_key, cache_version,
                            source_fingerprint=updated_fingerprint,
                            dependencies=validation.dependencies,
                            candidate_indexes=validation.candidate_indexes,
                        )
                        if touched:
                            store.prune(
                                cache_version,
                                max_entries=self.max_entries,
                                protected_keys=self._protected_keys(store_key),
                            )
                            return touched.result
            if entry:
                store.remove(cache_key)
            with self._lock:
                self._inflight[operation_key] = self._inflight.get(operation_key, 0) + 1
            try:
                snapshot = snapshot_builder() if snapshot_builder is not None else None
                if snapshot is not None:
                    source_fingerprint = snapshot.dependency_fingerprint
                result = builder()
                with self._lock:
                    if generation == self._generation:
                        store.save(
                            cache_key, cache_version, source_fingerprint, result,
                            protected_keys=self._protected_keys(store_key),
                            max_entries=self.max_entries,
                            dependencies=snapshot.dependencies if snapshot else None,
                            candidate_indexes=snapshot.candidate_indexes if snapshot else None,
                        )
                return result
            finally:
                with self._lock:
                    count = self._inflight.get(operation_key, 0)
                    if count <= 1:
                        self._inflight.pop(operation_key, None)
                    else:
                        self._inflight[operation_key] = count - 1
                    store.prune(
                        cache_version,
                        max_entries=self.max_entries,
                        protected_keys=self._protected_keys(store_key),
                    )

    def current_generation(self) -> int:
        with self._lock:
            return self._generation

    def clear_all(self, cache_dir: str) -> int:
        with self._lock:
            self._generation += 1
            return self._store(cache_dir).clear_all()

    def _store(self, cache_dir: str) -> ReportParsingCacheRepository:
        key = self._store_key(cache_dir)
        store = self._stores.get(key)
        if store is None:
            store = ReportParsingCacheRepository(cache_dir, clock=self._clock)
            self._stores[key] = store
        return store

    @staticmethod
    def _store_key(cache_dir: str) -> str:
        normalized = os.path.normcase(
            os.path.normpath(str(Path(cache_dir).resolve(strict=False)))
        ).casefold()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _key_lock(self, operation_key: str) -> threading.Lock:
        with self._lock:
            lock = self._key_locks.get(operation_key)
            if lock is None:
                lock = threading.Lock()
                self._key_locks[operation_key] = lock
            return lock

    def _protected_keys(self, store_key: str) -> set[str]:
        prefix = f"{store_key}\0"
        protected: set[str] = set()
        for operation_key in self._inflight:
            if not operation_key.startswith(prefix):
                continue
            parts = operation_key.split("\0")
            if len(parts) >= 2:
                protected.add(parts[1])
        return protected


REPORT_PARSING_CACHE_SERVICE = ReportParsingCacheService()


def clear_report_parsing_cache(cache_dir: str) -> int:
    """Clear report parse results without touching archive outputs."""
    cleared = REPORT_PARSING_CACHE_SERVICE.clear_all(cache_dir)
    # Archive parse reuse is memory-only and has no RAR/Manifest ownership.
    from .archive_parse_runtime_service import clear_archive_parse_cache

    return cleared + clear_archive_parse_cache()


__all__ = [
    "REPORT_PARSING_CACHE_SERVICE",
    "ReportParsingCacheError",
    "ReportParsingCacheService",
    "clear_report_parsing_cache",
]
