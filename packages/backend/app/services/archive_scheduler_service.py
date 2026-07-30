"""Database-backed archive scheduling without a second queue."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from ..repository.archive_task_repository import ArchiveTaskRepository
from ..repository.workbench_constants import MAX_RUNNING_ARCHIVE_TASKS
from ..repository.workbench_errors import WorkbenchPersistenceError
from .archive_resource_admission_service import (
    ArchiveResourceAdmissionService,
    ArchiveResourceSnapshot,
)


@dataclass(frozen=True)
class ArchiveTaskClaim:
    task_id: str
    owner_token: str
    attempt_id: str
    revision: int


class ArchiveSchedulerService:
    """Claim eligible persisted tasks in priority/FIFO order."""

    def __init__(
        self,
        tasks: ArchiveTaskRepository,
        admission: ArchiveResourceAdmissionService,
        *,
        max_running: int = MAX_RUNNING_ARCHIVE_TASKS,
    ) -> None:
        if max_running <= 0:
            raise ValueError("ARCHIVE_CONCURRENCY_LIMIT_INVALID")
        self.tasks = tasks
        self.admission = admission
        self.max_running = max_running

    def claim_next(
        self, snapshot: ArchiveResourceSnapshot,
    ) -> ArchiveTaskClaim | None:
        for task in self.tasks.list_queued():
            attempt_id = (task.get("process_binding") or {}).get("staging_asset_id")
            if not attempt_id:
                self._record_wait(task, "ARCHIVE_ATTEMPT_REQUIRED")
                continue
            input_bytes = task.get("counters", {}).get("input_bytes", 0)
            decision = self.admission.evaluate(snapshot, input_bytes=input_bytes)
            if not decision.admitted:
                self._record_wait(task, decision.reason or "ARCHIVE_RESOURCE_WAIT")
                continue
            owner_token = str(uuid4())
            try:
                claimed = self.tasks.claim(
                    task["task_id"],
                    owner_token=owner_token,
                    attempt_id=str(attempt_id),
                    expected_revision=task["revision"],
                    max_running=self.max_running,
                )
            except WorkbenchPersistenceError as error:
                if error.code in {
                    "REVISION_CONFLICT",
                    "ARCHIVE_TASK_NOT_CLAIMABLE",
                }:
                    continue
                if error.code == "ARCHIVE_CONCURRENCY_LIMIT":
                    return None
                raise
            return ArchiveTaskClaim(
                claimed["task_id"], owner_token, str(attempt_id),
                claimed["revision"],
            )
        return None

    def _record_wait(self, task: dict, reason: str) -> None:
        if task.get("error_code") == reason:
            return
        try:
            self.tasks.update_state(task["task_id"], {
                "error_code": reason,
                "error_summary": "Archive task is waiting for resource admission.",
            }, task["revision"])
        except WorkbenchPersistenceError as error:
            if error.code != "REVISION_CONFLICT":
                raise
