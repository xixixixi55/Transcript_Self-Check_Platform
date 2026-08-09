"""Bounded in-process execution for persistent case parsing tasks."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event, Lock, Timer, current_thread
from typing import Any


class CaseParseDispatcher:
    """Submit parsing after persistence without tying it to an HTTP response."""

    def __init__(
        self,
        max_workers: int = 2,
        source_verification_workers: int = 1,
        source_verification_max_attempts: int = 3,
        source_verification_retry_delay_seconds: float = 1.0,
    ) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="workbench-parse",
        )
        self._source_executor = ThreadPoolExecutor(
            max_workers=source_verification_workers,
            thread_name_prefix="workbench-source-verification",
        )
        self._source_verification_max_attempts = max(
            1, source_verification_max_attempts,
        )
        self._source_verification_retry_delay_seconds = max(
            0.0, source_verification_retry_delay_seconds,
        )
        self._lock = Lock()
        self._active: set[tuple[str, ...]] = set()
        self._retry_timers: set[Timer] = set()
        self._shutdown = False
        self._shutdown_event = Event()

    def dispatch(self, cases: Any, case_id: str, task_id: str) -> None:
        with self._lock:
            if self._shutdown:
                return
            task = cases.tasks.get(task_id)
            if not task.get("status") == "queued":
                return
            key = ("parse", case_id, task_id, str(task.get("attempt", 0)))
            if key in self._active:
                return
            self._active.add(key)
            try:
                future = self._executor.submit(self._run, cases, case_id, task_id)
            except Exception:
                self._active.remove(key)
                raise
        future.add_done_callback(lambda _future: self._forget(key))

    def dispatch_source_verification(
        self,
        sources: Any,
        source_id: str,
        source_revision: int | None = None,
        attempt: int = 1,
    ) -> None:
        """Verify the full source after parsing, outside the review path."""
        key = ("source-verification", f"{source_id}:{source_revision or 0}", str(attempt))
        with self._lock:
            if self._shutdown:
                return
            if key in self._active:
                return
            self._active.add(key)
            try:
                future = self._source_executor.submit(
                    self._run_source_verification,
                    sources,
                    source_id,
                    source_revision,
                    self._shutdown_event,
                )
            except Exception:
                self._active.remove(key)
                raise
        future.add_done_callback(
            lambda completed: self._complete_source_verification(
                completed, sources, source_id, attempt, key,
            ),
        )

    def _run(self, cases: Any, case_id: str, task_id: str) -> None:
        try:
            cases.run_parse_task(case_id, task_id)
            if cases.tasks.get(task_id).get("status") == "succeeded":
                source_id = cases.shells.get(case_id)["source_id"]
                source_revision = cases.sources.get(source_id)["revision"]
                self.dispatch_source_verification(cases.sources, source_id, source_revision)
        except Exception:
            try:
                cases.mark_dispatch_failed(case_id, task_id)
            except Exception:
                pass

    @staticmethod
    def _run_source_verification(
        sources: Any,
        source_id: str,
        source_revision: int | None,
        cancellation_event: Event,
    ) -> dict[str, Any]:
        return sources.verify_after_parse(
            source_id,
            expected_revision=source_revision,
            cancellation_event=cancellation_event,
        )

    def _complete_source_verification(
        self,
        future: Future[dict[str, Any]],
        sources: Any,
        source_id: str,
        attempt: int,
        key: tuple[str, ...],
    ) -> None:
        self._forget(key)
        try:
            result = future.result()
        except Exception:
            try:
                current = sources.get(source_id)
                if current.get("access_status") != "pending":
                    return
                result = sources.mark_verification_pending(
                    source_id,
                    "SOURCE_REVALIDATION_WORKER_FAILED",
                    int(current["revision"]),
                )
            except Exception:
                return
        if result.get("access_status") != "pending":
            return
        if attempt >= self._source_verification_max_attempts:
            try:
                sources.mark_verification_pending(
                    source_id,
                    "SOURCE_REVALIDATION_RETRY_EXHAUSTED",
                    int(result["revision"]),
                )
            except Exception:
                pass
            return
        self._schedule_source_verification_retry(
            sources, source_id, int(result["revision"]), attempt + 1,
        )

    def _schedule_source_verification_retry(
        self, sources: Any, source_id: str, source_revision: int, attempt: int,
    ) -> None:
        delay = self._source_verification_retry_delay_seconds * (2 ** (attempt - 2))
        timer = Timer(
            delay,
            self._retry_source_verification,
            args=(sources, source_id, source_revision, attempt),
        )
        timer.daemon = True
        with self._lock:
            if self._shutdown:
                return
            self._retry_timers.add(timer)
        timer.start()

    def _retry_source_verification(
        self, sources: Any, source_id: str, source_revision: int, attempt: int,
    ) -> None:
        with self._lock:
            self._retry_timers.discard(current_thread())
            if self._shutdown:
                return
        self.dispatch_source_verification(sources, source_id, source_revision, attempt)

    def _forget(self, key: tuple[str, ...]) -> None:
        with self._lock:
            self._active.discard(key)

    def shutdown(self, wait: bool = False) -> None:
        """Release executor resources for tests or an explicit app shutdown."""
        with self._lock:
            self._shutdown = True
            self._shutdown_event.set()
            timers = tuple(self._retry_timers)
            self._retry_timers.clear()
        for timer in timers:
            timer.cancel()
        self._executor.shutdown(wait=wait, cancel_futures=True)
        self._source_executor.shutdown(wait=wait, cancel_futures=True)
