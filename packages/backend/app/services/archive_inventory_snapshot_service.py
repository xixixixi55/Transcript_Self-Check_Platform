"""Short-lived metadata snapshots used only while building preview contexts."""

from __future__ import annotations

import hashlib
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
import weakref

from ..repository.archive_input_metadata_repository import metadata_fingerprint_for_directory


ARCHIVE_INVENTORY_CACHE_LIMIT = 16


class ArchiveInventorySnapshotStore:
    """Reuse immutable preview inventory without weakening archive execution."""

    def __init__(self, *, ttl_seconds: int) -> None:
        self._ttl_seconds = ttl_seconds
        self._snapshots: dict[str, tuple[float, object]] = {}
        self._locks: weakref.WeakValueDictionary[str, threading.Lock] = weakref.WeakValueDictionary()
        self._lock = threading.RLock()

    def get_or_build(
        self,
        key: str,
        builder: Callable[[], object],
        *,
        is_current: Callable[[object], bool] | None = None,
    ) -> object:
        lock = self._key_lock(key)
        with lock:
            now = time.time()
            with self._lock:
                self.cleanup(now)
                snapshot = self._snapshots.get(key)
                if snapshot is not None and (
                    is_current is None or is_current(snapshot[1])
                ):
                    return snapshot[1]
            value = builder()
            with self._lock:
                self._snapshots[key] = (time.time(), value)
                self._prune()
            return value

    @staticmethod
    def cache_key(source_key: str, output_root: str) -> str:
        normalized_output = os.path.normcase(
            os.path.normpath(str(Path(output_root).resolve(strict=False)))
        ).casefold()
        output_key = hashlib.sha256(normalized_output.encode("utf-8")).hexdigest()
        return f"{source_key}\0{output_key}"

    def cleanup(self, now: float | None = None) -> None:
        current = time.time() if now is None else now
        with self._lock:
            expired = [
                key for key, (created_at, _) in self._snapshots.items()
                if created_at + self._ttl_seconds <= current
            ]
            for key in expired:
                self._snapshots.pop(key, None)

    def _key_lock(self, key: str) -> threading.Lock:
        with self._lock:
            lock = self._locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._locks[key] = lock
            return lock

    def _prune(self) -> None:
        while len(self._snapshots) > ARCHIVE_INVENTORY_CACHE_LIMIT:
            oldest = min(
                self._snapshots,
                key=lambda key: self._snapshots[key][0],
            )
            self._snapshots.pop(oldest, None)


def inventory_snapshot_is_current(inventory: object) -> bool:
    fingerprint = str(getattr(inventory, "metadata_fingerprint", ""))
    if not fingerprint:
        return False
    return metadata_fingerprint_for_directory(
        inventory.source_root, inventory.output_root,
    ) == fingerprint


__all__ = ["ArchiveInventorySnapshotStore", "inventory_snapshot_is_current"]
