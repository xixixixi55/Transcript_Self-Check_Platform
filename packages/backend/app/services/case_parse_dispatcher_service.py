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
        self._active: set[tuple[str, ...]] = set()

    def dispatch(self, cases: Any, case_id: str, task_id: str) -> None:
        with self._lock:
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

    def dispatch_source_verification(self, sources: Any, source_id: str, source_revision: int | None = None) -> None:
        """Verify the full source after parsing, outside the review path."""
        key = ("source-verification", f"{source_id}:{source_revision or 0}")
        with self._lock:
            if key in self._active:
                return
            self._active.add(key)
            try:
                future = self._executor.submit(self._run_source_verification, sources, source_id, source_revision)
            except Exception:
                self._active.remove(key)
                raise
            future.add_done_callback(lambda _future: self._forget(key))

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
    def _run_source_verification(sources: Any, source_id: str, source_revision: int | None) -> None:
        sources.verify_after_parse(source_id, expected_revision=source_revision)

    def _forget(self, key: tuple[str, ...]) -> None:
        with self._lock:
            self._active.discard(key)

    def shutdown(self, wait: bool = False) -> None:
        """Release executor resources for tests or an explicit app shutdown."""
        self._executor.shutdown(wait=wait, cancel_futures=True)
