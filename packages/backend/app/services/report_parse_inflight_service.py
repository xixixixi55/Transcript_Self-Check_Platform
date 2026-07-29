"""Layer 21: bounded same-directory Parser task sharing."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
import threading
import time
from collections.abc import Callable
from typing import TypeVar


T = TypeVar("T")


class ReportParseInFlightError(RuntimeError):
    """Safe diagnostics for a shared Parser task lifecycle."""


class ReportParseInFlightCapacityError(ReportParseInFlightError):
    """The bounded registry cannot accept another distinct report task."""


class ReportParseWaitTimeout(ReportParseInFlightError):
    """A caller detached from a shared task while it continued in the backend."""


@dataclass(frozen=True)
class _InFlightEntry:
    created_at: float
    future: Future[object]


class ReportParseInFlightRegistry:
    """Share one background task for each opaque parse identity."""

    def __init__(
        self,
        *,
        max_entries: int = 8,
        max_lifetime_seconds: float = 900.0,
        clock: Callable[[], float] = time.monotonic,
        executor: ThreadPoolExecutor | None = None,
    ) -> None:
        if max_entries < 1 or max_lifetime_seconds <= 0:
            raise ValueError("Parser in-flight limits are invalid.")
        self.max_entries = max_entries
        self.max_lifetime_seconds = max_lifetime_seconds
        self._clock = clock
        self._lock = threading.RLock()
        self._entries: dict[str, _InFlightEntry] = {}
        self._completing: dict[str, _InFlightEntry] = {}
        self._executor = executor or ThreadPoolExecutor(
            max_workers=max_entries,
            thread_name_prefix="report-parse",
        )

    def run(
        self,
        key: str,
        builder: Callable[[], T],
        *,
        wait_timeout: float | None = None,
    ) -> T:
        if not key:
            raise ReportParseInFlightError("Parser task identity is invalid.")
        with self._lock:
            self._cleanup_locked()
            entry = self._entries.get(key) or self._completing.get(key)
            if entry is None:
                if len(self._entries) >= self.max_entries:
                    raise ReportParseInFlightCapacityError("解析任务容量已满，请稍后重试。")
                promise: Future[object] = Future()
                entry = _InFlightEntry(self._clock(), promise)
                self._entries[key] = entry
                try:
                    self._executor.submit(self._execute, key, builder, entry)
                except BaseException:
                    self._entries.pop(key, None)
                    raise ReportParseInFlightError("解析任务无法启动。")
        remaining_lifetime = self._remaining_lifetime(entry)
        if remaining_lifetime <= 0 and not entry.future.done():
            raise ReportParseWaitTimeout("Parser task lifetime expired.")
        timeout = remaining_lifetime if wait_timeout is None else min(
            wait_timeout, remaining_lifetime,
        )
        try:
            return entry.future.result(timeout=timeout)
        except TimeoutError as error:
            raise ReportParseWaitTimeout("解析任务等待已取消。") from error

    @property
    def active_count(self) -> int:
        with self._lock:
            self._cleanup_locked()
            return len(self._entries)

    def _execute(
        self,
        key: str,
        builder: Callable[[], T],
        entry: _InFlightEntry,
    ) -> None:
        promise = entry.future
        result: object | None = None
        error: BaseException | None = None
        try:
            result = builder()
        except BaseException as caught:
            error = caught
        with self._lock:
            current = self._entries.get(key)
            if current is not None and current is entry:
                self._entries.pop(key, None)
                self._completing[key] = entry
        try:
            if error is not None:
                promise.set_exception(error)
            else:
                promise.set_result(result)
        finally:
            with self._lock:
                current = self._completing.get(key)
                if current is entry:
                    self._completing.pop(key, None)

    def _cleanup_locked(self) -> None:
        expired = [key for key, entry in self._entries.items() if entry.future.done()]
        for key in expired:
            self._entries.pop(key, None)

    def _remaining_lifetime(self, entry: _InFlightEntry) -> float:
        return max(
            0.0,
            self.max_lifetime_seconds - (self._clock() - entry.created_at),
        )


REPORT_PARSE_INFLIGHT_REGISTRY = ReportParseInFlightRegistry()


__all__ = [
    "REPORT_PARSE_INFLIGHT_REGISTRY", "ReportParseInFlightCapacityError",
    "ReportParseInFlightError", "ReportParseInFlightRegistry",
    "ReportParseWaitTimeout",
]
