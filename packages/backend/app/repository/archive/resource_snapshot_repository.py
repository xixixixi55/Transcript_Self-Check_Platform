"""不使用工作进程循环的受控归档心跳和活动持久化。"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from .archive_task_repository import ArchiveTaskRepository
from ..workbench.workbench_constants import ARCHIVE_ACTIVITY_PERSIST_INTERVAL_SECONDS
from ..workbench.workbench_database import WorkbenchDatabase, normalize_utc
from ..workbench.workbench_errors import RevisionConflictError, WorkbenchPersistenceError


class ResourceSnapshotRepository:
    def __init__(
        self,
        database: WorkbenchDatabase,
        interval_seconds: int = ARCHIVE_ACTIVITY_PERSIST_INTERVAL_SECONDS,
    ) -> None:
        self.tasks = ArchiveTaskRepository(database)
        self.interval_seconds = interval_seconds

    def persist(
        self, task_id: str, snapshot: Mapping[str, Any], expected_revision: int
    ) -> dict[str, Any]:
        current = self.tasks.get(task_id)
        if current["revision"] != expected_revision:
            raise RevisionConflictError("task", expected_revision, current["revision"])
        if current["status"] != "running":
            raise WorkbenchPersistenceError("ARCHIVE_ACTIVITY_NOT_WRITABLE")
        at = normalize_utc(snapshot.get("observed_at"))
        output_bytes = snapshot.get("output_bytes", current["output_bytes"])
        volume_count = snapshot.get("output_volume_count", current["output_volume_count"])
        _metric(output_bytes)
        _metric(volume_count)
        output_changed = (
            output_bytes != current["output_bytes"]
            or volume_count != current["output_volume_count"]
        )
        baseline = current["last_heartbeat_at"] or current["updated_at"]
        if not output_changed and _seconds_between(baseline, at) < self.interval_seconds:
            return current
        changes = {
            "last_heartbeat_at": at, "output_bytes": output_bytes,
            "output_volume_count": volume_count, "updated_at": at,
        }
        if output_changed:
            changes["last_output_change_at"] = at
        return self.tasks.tasks.update(task_id, changes, expected_revision)


def _seconds_between(earlier: str, later: str) -> float:
    return (
        datetime.fromisoformat(later.replace("Z", "+00:00"))
        - datetime.fromisoformat(earlier.replace("Z", "+00:00"))
    ).total_seconds()


def _metric(value: Any) -> None:
    if value is not None and (
        isinstance(value, bool) or not isinstance(value, int) or value < 0
    ):
        raise WorkbenchPersistenceError("INVALID_TASK_PROGRESS")
