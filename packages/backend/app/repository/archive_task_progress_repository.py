"""Archive task milestone validation helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .workbench_constants import ARCHIVE_WORKFLOW_MILESTONES
from .workbench_errors import WorkbenchPersistenceError


def milestone(stage: str) -> tuple[int, str]:
    try:
        return ARCHIVE_WORKFLOW_MILESTONES[stage]
    except KeyError as error:
        raise WorkbenchPersistenceError("INVALID_ARCHIVE_STAGE") from error


def stage_index(stage: str) -> int:
    return list(ARCHIVE_WORKFLOW_MILESTONES).index(stage) + 1


def validate_milestone(task: Mapping[str, Any]) -> None:
    if task.get("progress_kind") != "workflow_milestone":
        raise WorkbenchPersistenceError("INVALID_TASK_PROGRESS")
    if task.get("percent") != milestone(str(task.get("stage")))[0]:
        raise WorkbenchPersistenceError("INVALID_TASK_PROGRESS")
