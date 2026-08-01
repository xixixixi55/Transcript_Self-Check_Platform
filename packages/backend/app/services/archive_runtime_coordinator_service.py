"""FastAPI-lifespan-owned coordination over the durable archive queue."""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, wait
from typing import Any, Callable

from ..repository.archive_attempt_restart_repository import interrupt_owned_claim
from ..repository.workbench_errors import WorkbenchPersistenceError
from .archive_attempt_service import ArchiveAttemptService
from .archive_progress_service import ArchiveProgressService
from .archive_resource_admission_service import ArchiveResourceSnapshot
from .archive_scheduler_service import ArchiveSchedulerService, ArchiveTaskClaim
from .archive_worker_service import ArchiveWorkerService

WorkItemFactory = Callable[[ArchiveTaskClaim, str], Any]
SnapshotProvider = Callable[[], ArchiveResourceSnapshot]
logger = logging.getLogger(__name__)


class ArchiveRuntimeCoordinator:
    """Own one bounded scheduler loop; persistence remains the queue authority."""

    def __init__(
        self,
        scheduler: ArchiveSchedulerService,
        worker: ArchiveWorkerService,
        attempts: ArchiveAttemptService,
        progress: ArchiveProgressService,
        *,
        item_factory: WorkItemFactory,
        snapshot_provider: SnapshotProvider,
        poll_interval_seconds: float = 1.0,
        shutdown_timeout_seconds: float = 30.0,
        max_workers: int = 6,
    ) -> None:
        if poll_interval_seconds <= 0 or shutdown_timeout_seconds <= 0 or max_workers <= 0:
            raise ValueError("ARCHIVE_RUNTIME_CONFIG_INVALID")
        self.scheduler = scheduler
        self.worker = worker
        self.attempts = attempts
        self.progress = progress
        self.item_factory = item_factory
        self.snapshot_provider = snapshot_provider
        self.poll_interval_seconds = poll_interval_seconds
        self.shutdown_timeout_seconds = shutdown_timeout_seconds
        self.max_workers = max_workers
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._contexts: dict[str, str] = {}
        self._futures: set[Future[Any]] = set()
        self._claims: dict[Future[Any], ArchiveTaskClaim] = {}
        self._executor: ThreadPoolExecutor | None = None
        self._thread: threading.Thread | None = None
        self.loop_start_count = 0

    @property
    def is_running(self) -> bool:
        with self._lock:
            return bool(self._thread and self._thread.is_alive())

    def register(self, task_id: str, context_id: str) -> None:
        with self._lock:
            self._contexts[task_id] = context_id

    def unregister(self, task_id: str) -> None:
        with self._lock:
            self._contexts.pop(task_id, None)

    def start(self) -> bool:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            self._collect_finished()
            if self._futures:
                return False
            self._stop.clear()
            self._executor = ThreadPoolExecutor(
                max_workers=self.max_workers,
                thread_name_prefix="archive-worker",
            )
            self._thread = threading.Thread(
                target=self._run_loop,
                name="archive-scheduler",
                daemon=True,
            )
            self.loop_start_count += 1
            self._thread.start()
            return True

    def stop(self) -> bool:
        self._collect_finished()
        with self._lock:
            thread = self._thread
            executor = self._executor
            futures = set(self._futures)
        if thread is None and not futures:
            return True
        self._stop.set()
        deadline = time.monotonic() + self.shutdown_timeout_seconds
        if thread is not None:
            thread.join(max(0.0, deadline - time.monotonic()))
        if futures:
            _, pending = wait(futures, timeout=max(0.0, deadline - time.monotonic()))
        else:
            pending = set()
        if executor is not None:
            executor.shutdown(wait=not pending, cancel_futures=True)
        converged = True
        for future in pending | {item for item in futures if item.cancelled()}:
            with self._lock:
                claim = self._claims.get(future)
            if claim is not None:
                converged = self._finish_interrupted(claim) and converged
        self._collect_finished()
        with self._lock:
            remaining = {future for future in self._futures if not future.done()}
            stopped = (thread is None or not thread.is_alive()) and not remaining and converged
            if stopped:
                self._thread = None
                self._executor = None
                self._futures.clear()
                self._claims.clear()
        return stopped

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            self._collect_finished()
            submitted = False
            while not self._stop.is_set() and self._active_count() < self.max_workers:
                try:
                    claim = self.scheduler.claim_next(self.snapshot_provider())
                except Exception:
                    logger.exception("Archive scheduler iteration failed safely.")
                    break
                if claim is None:
                    break
                with self._lock:
                    context_id = self._contexts.pop(claim.task_id, "")
                    executor = self._executor
                if executor is None:
                    self._finish_interrupted(claim)
                    break
                try:
                    future = executor.submit(self._run_claim, claim, context_id)
                except RuntimeError:
                    self._finish_interrupted(claim)
                    break
                with self._lock:
                    self._futures.add(future)
                    self._claims[future] = claim
                submitted = True
            if not submitted:
                self._stop.wait(self.poll_interval_seconds)
        self._collect_finished()

    def _run_claim(self, claim: ArchiveTaskClaim, context_id: str) -> None:
        try:
            if not context_id:
                raise WorkbenchPersistenceError("ARCHIVE_RUNTIME_CONTEXT_UNAVAILABLE")
            item = self.item_factory(claim, context_id)
            self.worker.run(
                claim, item, interruption_check=self._stop.is_set,
            )
        except Exception as error:
            self._finish_unhandled(claim, error)

    def _finish_unhandled(self, claim: ArchiveTaskClaim, error: Exception) -> None:
        try:
            if self._stop.is_set():
                self._finish_interrupted(claim)
                return
            code = getattr(error, "code", "ARCHIVE_RUNTIME_EXECUTION_FAILED")
            try:
                self.attempts.fail(claim.attempt_id, str(code))
            except WorkbenchPersistenceError:
                pass
            self.progress.fail(
                claim.task_id,
                claim.owner_token,
                error_code=str(code),
                error_summary="Archive execution failed safely.",
                retryable=True,
            )
        except WorkbenchPersistenceError:
            pass

    def _finish_interrupted(self, claim: ArchiveTaskClaim) -> bool:
        try:
            result = interrupt_owned_claim(
                self.attempts.database, task_id=claim.task_id,
                owner_token=claim.owner_token, attempt_id=claim.attempt_id,
                task_revision=claim.revision,
            )
            if result == "unresolved":
                logger.error("Archive shutdown could not converge claim %s", claim.task_id)
                return False
            return True
        except WorkbenchPersistenceError:
            logger.exception("Archive shutdown claim settlement failed: %s", claim.task_id)
            return False

    def _collect_finished(self) -> None:
        with self._lock:
            finished = {future for future in self._futures if future.done()}
            self._futures.difference_update(finished)
            for future in finished:
                self._claims.pop(future, None)

    def _active_count(self) -> int:
        with self._lock:
            return sum(not future.done() for future in self._futures)
