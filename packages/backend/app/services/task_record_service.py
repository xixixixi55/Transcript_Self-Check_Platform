"""Task status queries and conservative cancellation/recovery controls."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..repository.case_workflow_repository import CaseWorkflowRepository
from ..repository.task_record_repository import TaskRecordRepository
from ..repository.workbench_database import WorkbenchDatabase
from ..repository.workbench_errors import WorkbenchPersistenceError


class TaskRecordService:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.repository = TaskRecordRepository(database)
        self.workflow = CaseWorkflowRepository(database)

    def get(self, task_id: str) -> dict[str, Any]:
        return self.repository.get(task_id)

    def request_cancel(self, task_id: str, expected_revision: int) -> dict[str, Any]:
        current = self.repository.get(task_id)
        if current["status"] not in {"queued", "running"}:
            raise WorkbenchPersistenceError("TASK_NOT_CANCELLABLE")
        self.workflow.cancel_parse(current["case_id"], task_id, expected_revision)
        return self.repository.get(task_id)

    def recover_after_restart(self, *, include_archive: bool = True) -> list[str]:
        return self.workflow.recover_after_restart(include_archive=include_archive)

    def retryable(self, task: Mapping[str, Any]) -> bool:
        return task.get("kind") == "parse" and task.get("status") in {"failed_retryable", "interrupted"}
