"""Bounded in-process execution for persistent case parsing tasks."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Any


class CaseParseDispatcher:
    """Submit parsing after persistence without tying it to an HTTP response."""

    def __init__(self, max_workers: int = 2) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="workbench-parse",
        )
        self._lock = Lock()
        self._active: set[tuple[str, str]] = set()

    def dispatch(self, cases: Any, case_id: str, task_id: str) -> None:
        key = (case_id, task_id)
        with self._lock:
            if key in self._active or not self._is_queued(cases, task_id):
                return
            self._active.add(key)
            try:
                future = self._executor.submit(self._run, cases, case_id, task_id)
            except Exception:
                self._active.remove(key)
                raise
            future.add_done_callback(lambda _future: self._forget(key))

    def dispatch_source_verification(self, sources: Any, source_id: str) -> None:
        """Verify the full source after parsing, outside the review path."""
        key = ("source-verification", source_id)
        with self._lock:
            if key in self._active:
                return
            self._active.add(key)
            try:
                future = self._executor.submit(self._run_source_verification, sources, source_id)
            except Exception:
                self._active.remove(key)
                raise
            future.add_done_callback(lambda _future: self._forget(key))

    @staticmethod
    def _is_queued(cases: Any, task_id: str) -> bool:
        task = cases.tasks.get(task_id)
        return task.get("status") == "queued"

    def _run(self, cases: Any, case_id: str, task_id: str) -> None:
        try:
            cases.run_parse_task(case_id, task_id)
            if cases.tasks.get(task_id).get("status") == "succeeded":
                source_id = cases.shells.get(case_id)["source_id"]
                self.dispatch_source_verification(cases.sources, source_id)
        except Exception:
            try:
                cases.mark_dispatch_failed(case_id, task_id)
            except Exception:
                pass

    @staticmethod
    def _run_source_verification(sources: Any, source_id: str) -> None:
        sources.verify_after_parse(source_id)

    def _forget(self, key: tuple[str, str]) -> None:
        with self._lock:
            self._active.discard(key)

    def shutdown(self, wait: bool = False) -> None:
        """Release executor resources for tests or an explicit app shutdown."""
        self._executor.shutdown(wait=wait, cancel_futures=True)
