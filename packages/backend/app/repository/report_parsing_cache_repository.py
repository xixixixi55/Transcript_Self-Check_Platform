"""Atomic, path-free persistence for report parsing cache entries."""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_KEY_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_TEMP_PREFIX = ".report-parsing-cache-"


class ReportParsingCacheError(RuntimeError):
    """Safe cache storage diagnostics without local paths or report data."""


@dataclass(frozen=True)
class ReportCacheEntry:
    cache_key: str
    cache_version: int
    source_fingerprint: str
    last_accessed_at: float
    result: dict[str, object]


class ReportParsingCacheRepository:
    """Store only report-cache files; never reaches compressed or export roots."""

    def __init__(self, cache_dir: str | os.PathLike[str], clock=time.time) -> None:
        self.cache_dir = Path(cache_dir)
        self._clock = clock
        self._lock = threading.RLock()

    def load(self, cache_key: str, cache_version: int) -> ReportCacheEntry | None:
        with self._lock:
            path = self._path_for_key(cache_key)
            if not path.is_file():
                return None
            try:
                payload = self._read_payload(path)
            except ReportParsingCacheError:
                self._remove(path)
                return None
            entry = self._parse_entry(payload, cache_key, cache_version)
            if entry is None:
                self._remove(path)
            return entry

    def remove(self, cache_key: str) -> None:
        with self._lock:
            path = self._path_for_key(cache_key)
            if path.exists():
                self._remove(path)

    def touch(self, cache_key: str, cache_version: int) -> ReportCacheEntry | None:
        with self._lock:
            path = self._path_for_key(cache_key)
            if not path.is_file():
                return None
            try:
                payload = self._read_payload(path)
            except ReportParsingCacheError:
                self._remove(path)
                return None
            entry = self._parse_entry(payload, cache_key, cache_version)
            if entry is None:
                self._remove(path)
                return None
            updated = dict(payload)
            updated["last_accessed_at"] = float(self._clock())
            self._write_payload(path, updated)
            return ReportCacheEntry(
                entry.cache_key, entry.cache_version, entry.source_fingerprint,
                float(updated["last_accessed_at"]), entry.result,
            )

    def save(
        self,
        cache_key: str,
        cache_version: int,
        source_fingerprint: str,
        result: dict[str, object],
        *,
        protected_keys: Iterable[str] = (),
        max_entries: int = 5,
    ) -> None:
        with self._lock:
            path = self._path_for_key(cache_key)
            payload = {
                "cache_key": cache_key,
                "cache_version": cache_version,
                "source_fingerprint": source_fingerprint,
                "last_accessed_at": float(self._clock()),
                "result": result,
            }
            self._write_payload(path, payload)
            self.prune(
                cache_version, max_entries=max_entries,
                protected_keys=protected_keys,
            )

    def prune(
        self,
        cache_version: int,
        *,
        max_entries: int = 5,
        protected_keys: Iterable[str] = (),
    ) -> None:
        if max_entries < 1:
            raise ReportParsingCacheError("解析缓存上限无效。")
        with self._lock:
            protected = set(protected_keys)
            entries: list[ReportCacheEntry] = []
            for path in self._entry_files():
                try:
                    payload = self._read_payload(path)
                except ReportParsingCacheError:
                    self._remove(path)
                    continue
                entry = self._parse_entry(payload, path.stem, cache_version)
                if entry is None:
                    self._remove(path)
                else:
                    entries.append(entry)
            overflow = len(entries) - max_entries
            if overflow <= 0:
                return
            ordered = sorted(entries, key=lambda item: (item.last_accessed_at, item.cache_key))
            for entry in ordered:
                if overflow <= 0:
                    break
                if entry.cache_key in protected:
                    continue
                self._remove(self._path_for_key(entry.cache_key))
                overflow -= 1

    def clear_all(self) -> int:
        """Delete only cache entry JSON and abandoned cache temp files."""
        with self._lock:
            if not self.cache_dir.exists():
                return 0
            cleared = 0
            try:
                files = list(self.cache_dir.iterdir())
            except OSError as error:
                raise ReportParsingCacheError("解析缓存目录无法读取。") from error
            for path in files:
                if not path.is_file():
                    continue
                is_entry = path.suffix.casefold() == ".json"
                is_temp = path.name.startswith(_TEMP_PREFIX)
                if not (is_entry or is_temp):
                    continue
                self._remove(path)
                if is_entry:
                    cleared += 1
            return cleared

    def _entry_files(self) -> list[Path]:
        if not self.cache_dir.exists():
            return []
        try:
            return [
                path for path in self.cache_dir.iterdir()
                if path.is_file() and path.suffix.casefold() == ".json"
            ]
        except OSError as error:
            raise ReportParsingCacheError("解析缓存目录无法读取。") from error

    def _path_for_key(self, cache_key: str) -> Path:
        if not _KEY_PATTERN.fullmatch(cache_key):
            raise ReportParsingCacheError("解析缓存键无效。")
        return self.cache_dir / f"{cache_key}.json"

    @staticmethod
    def _parse_entry(
        payload: object, cache_key: str, cache_version: int,
    ) -> ReportCacheEntry | None:
        if not isinstance(payload, dict):
            return None
        version = payload.get("cache_version")
        source_fingerprint = payload.get("source_fingerprint")
        last_accessed_at = payload.get("last_accessed_at")
        result = payload.get("result")
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
        )

    @staticmethod
    def _read_payload(path: Path) -> dict[str, object]:
        try:
            with path.open("r", encoding="utf-8") as stream:
                payload = json.load(stream)
        except (OSError, ValueError, TypeError) as error:
            raise ReportParsingCacheError("解析缓存损坏。") from error
        return payload if isinstance(payload, dict) else {}

    def _write_payload(self, path: Path, payload: dict[str, object]) -> None:
        temporary: Path | None = None
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.cache_dir,
                prefix=_TEMP_PREFIX, suffix=".tmp", delete=False,
            ) as stream:
                temporary = Path(stream.name)
                json.dump(payload, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except (OSError, TypeError, ValueError) as error:
            raise ReportParsingCacheError("解析缓存无法保存。") from error
        finally:
            if temporary and temporary.exists():
                try:
                    temporary.unlink()
                except OSError:
                    pass

    @staticmethod
    def _remove(path: Path) -> None:
        try:
            path.unlink()
        except OSError as error:
            raise ReportParsingCacheError("解析缓存无法清理。") from error
