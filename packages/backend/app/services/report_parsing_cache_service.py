"""LRU orchestration for persistent report parsing results."""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from pathlib import Path

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
        self._key_locks: dict[str, threading.Lock] = {}
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
    ) -> dict[str, object]:
        cache_key = normalized_directory_key(source_dir)
        source_fingerprint = directory_content_fingerprint(fingerprint_dir or source_dir)
        store_key = self._store_key(cache_dir)
        operation_key = f"{store_key}\0{cache_key}"
        with self._key_lock(operation_key):
            store = self._store(cache_dir)
            with self._lock:
                entry = store.load(cache_key, cache_version)
                if entry and entry.source_fingerprint == source_fingerprint:
                    touched = store.touch(cache_key, cache_version)
                    if touched:
                        store.prune(
                            cache_version,
                            max_entries=self.max_entries,
                            protected_keys=self._protected_keys(store_key),
                        )
                        return touched.result
                elif entry:
                    store.remove(cache_key)
                generation = self._generation
                self._inflight[operation_key] = self._inflight.get(operation_key, 0) + 1
            try:
                result = builder()
                with self._lock:
                    if generation == self._generation:
                        store.save(
                            cache_key, cache_version, source_fingerprint, result,
                            protected_keys=self._protected_keys(store_key),
                            max_entries=self.max_entries,
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
        return os.path.normcase(os.path.normpath(str(Path(cache_dir).resolve(strict=False)))).casefold()

    def _key_lock(self, operation_key: str) -> threading.Lock:
        with self._lock:
            lock = self._key_locks.get(operation_key)
            if lock is None:
                lock = threading.Lock()
                self._key_locks[operation_key] = lock
            return lock

    def _protected_keys(self, store_key: str) -> set[str]:
        prefix = f"{store_key}\0"
        return {
            operation_key[len(prefix):]
            for operation_key in self._inflight
            if operation_key.startswith(prefix)
        }


REPORT_PARSING_CACHE_SERVICE = ReportParsingCacheService()


def clear_report_parsing_cache(cache_dir: str) -> int:
    """Clear only the configured report parsing cache directory."""
    return REPORT_PARSING_CACHE_SERVICE.clear_all(cache_dir)


__all__ = [
    "REPORT_PARSING_CACHE_SERVICE",
    "ReportParsingCacheError",
    "ReportParsingCacheService",
    "clear_report_parsing_cache",
]
