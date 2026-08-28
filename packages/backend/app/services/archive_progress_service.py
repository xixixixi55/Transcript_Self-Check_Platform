"""经验证工作流边界上的自有归档任务转换。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ..repository.archive_task_repository import ArchiveTaskRepository
from ..repository.resource_snapshot_repository import ResourceSnapshotRepository
from ..repository.workbench_errors import WorkbenchPersistenceError

_STAGES = (
    "queued", "inventory", "preflight_verified", "winrar", "integrity",
    "integrity_verified", "md5", "manifest", "completed",
)


class ArchiveProgressService:
    def __init__(
        self,
        tasks: ArchiveTaskRepository,
        snapshots: ResourceSnapshotRepository,
    ) -> None:
        self.tasks = tasks
        self.snapshots = snapshots

    def advance(
        self, task_id: str, owner_token: str, stage: str,
    ) -> dict[str, Any]:
        current = self._owned(task_id, owner_token, running_only=True)
        if stage == current["stage"]:
            return current
        try:
            current_index = _STAGES.index(current["stage"])
            next_index = _STAGES.index(stage)
        except ValueError as error:
            raise WorkbenchPersistenceError("INVALID_ARCHIVE_STAGE") from error
        if next_index != current_index + 1 or stage == "completed":
            raise WorkbenchPersistenceError("ARCHIVE_STAGE_GATE_REQUIRED")
        return self.tasks.update_state(task_id, {
            "stage": stage,
            "worker_state": "owned_running",
        }, current["revision"])

    def activity(
        self,
        task_id: str,
        owner_token: str,
        snapshot: Mapping[str, Any],
    ) -> dict[str, Any]:
        current = self._owned(task_id, owner_token, running_only=True)
        return self.snapshots.persist(task_id, snapshot, current["revision"])

    def request_cancel(
        self, task_id: str, expected_revision: int,
    ) -> dict[str, Any]:
        current = self.tasks.get(task_id)
        if current["revision"] != expected_revision:
            raise WorkbenchPersistenceError("REVISION_CONFLICT")
        if current["status"] == "blocked":
            cancelling = self.tasks.update_state(task_id, {
                "status": "cancelling", "cancel_requested": True,
            }, expected_revision)
            return self.tasks.update_state(task_id, {
                "status": "cancelled", "cancel_requested": True,
            }, cancelling["revision"])
        if current["status"] == "queued":
            return self.tasks.update_state(task_id, {
                "status": "cancelled", "cancel_requested": True,
            }, expected_revision)
        if current["status"] != "running":
            raise WorkbenchPersistenceError("ARCHIVE_CANCEL_NOT_ALLOWED")
        return self.tasks.update_state(task_id, {
            "status": "cancelling", "cancel_requested": True,
        }, expected_revision)

    def cancellation_requested(self, task_id: str, owner_token: str) -> bool:
        current = self._owned(task_id, owner_token)
        return bool(
            current["cancel_requested"] or current["status"] == "cancelling"
        )

    def cancel(self, task_id: str, owner_token: str) -> dict[str, Any]:
        current = self._owned(task_id, owner_token)
        if current["status"] not in {"running", "cancelling"}:
            raise WorkbenchPersistenceError("ARCHIVE_CANCEL_NOT_ALLOWED")
        return self.tasks.update_state(task_id, {
            "status": "cancelled",
            "cancel_requested": True,
            "worker_state": "released",
        }, current["revision"])

    def fail(
        self,
        task_id: str,
        owner_token: str,
        *,
        error_code: str,
        error_summary: str,
        retryable: bool = True,
    ) -> dict[str, Any]:
        current = self._owned(task_id, owner_token)
        return self.tasks.update_state(task_id, {
            "status": "failed_retryable" if retryable else "failed_terminal",
            "error_code": error_code,
            "error_summary": error_summary,
            "worker_state": "released",
        }, current["revision"])

    def complete(self, task_id: str, owner_token: str) -> dict[str, Any]:
        current = self._owned(task_id, owner_token, running_only=True)
        if current["stage"] != "manifest":
            raise WorkbenchPersistenceError("ARCHIVE_STAGE_GATE_REQUIRED")
        return self.tasks.update_state(task_id, {
            "status": "succeeded",
            "stage": "completed",
            "worker_state": "released",
        }, current["revision"])

    def _owned(
        self, task_id: str, owner_token: str, *, running_only: bool = False,
    ) -> dict[str, Any]:
        current = self.tasks.get(task_id)
        binding = current.get("process_binding") or {}
        if binding.get("process_tree_id") != owner_token:
            raise WorkbenchPersistenceError("ARCHIVE_TASK_OWNERSHIP_LOST")
        valid = {"running"} if running_only else {"running", "cancelling"}
        if current["status"] not in valid:
            raise WorkbenchPersistenceError("ARCHIVE_TASK_OWNERSHIP_LOST")
        return current
