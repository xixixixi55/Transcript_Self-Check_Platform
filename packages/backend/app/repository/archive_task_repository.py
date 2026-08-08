"""Archive task state, selection, restart projection, and safe card summaries."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .task_record_repository import TaskRecordRepository
from .archive_task_progress_repository import milestone as _milestone
from .archive_task_progress_repository import stage_index as _stage_index
from .archive_task_progress_repository import validate_milestone as _validate_milestone
from .workbench_constants import ARCHIVE_TASK_ACTIONS, ARCHIVE_WORKFLOW_MILESTONES
from .workbench_database import WorkbenchDatabase, utc_now
from .workbench_errors import RevisionConflictError, WorkbenchPersistenceError
from .workbench_repository_helpers import json_text, row_json
from .workbench_serialization import validate_opaque_id
from .archive_task_projection_repository import build_archive_task_card_summary, safe_error

_ACTIVE = ("queued", "running", "cancelling", "blocked")


class ArchiveTaskRepository:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database
        self.tasks = TaskRecordRepository(database)

    def create(self, task: Mapping[str, Any]) -> dict[str, Any]:
        stage = str(task.get("stage", "queued"))
        milestone = _milestone(stage)
        status = str(task.get("status", "queued"))
        value = {
            **task, "kind": "archive", "status": status, "stage": stage,
            "deployment_instance_id": task.get(
                "deployment_instance_id", self.database.deployment_instance_id,
            ),
            "percent": task.get("percent", milestone[0]),
            "progress_kind": "workflow_milestone", "stage_label": milestone[1],
            "stage_index": _stage_index(stage),
            "stage_count": len(ARCHIVE_WORKFLOW_MILESTONES),
            "worker_state": task.get("worker_state", "unassigned"),
            "allowed_actions": ARCHIVE_TASK_ACTIONS[status],
        }
        if value["deployment_instance_id"] != self.database.deployment_instance_id:
            raise WorkbenchPersistenceError("ARCHIVE_DEPLOYMENT_MISMATCH")
        _validate_milestone(value)
        return self.tasks.create(value)

    def get(self, task_id: str) -> dict[str, Any]:
        task = self.tasks.get(task_id)
        if task["kind"] != "archive":
            raise WorkbenchPersistenceError("ARCHIVE_TASK_NOT_FOUND")
        if task.get("deployment_instance_id") != self.database.deployment_instance_id:
            raise WorkbenchPersistenceError("ARCHIVE_TASK_NOT_FOUND")
        return task

    def bind_attempt(self, task_id: str, attempt_id: str) -> dict[str, Any]:
        from .archive_task_binding_repository import bind_archive_task_attempt
        bind_archive_task_attempt(self.database, task_id, attempt_id)
        return self.get(task_id)

    def update_state(
        self, task_id: str, changes: Mapping[str, Any], expected_revision: int
    ) -> dict[str, Any]:
        current = self.get(task_id)
        stage = str(changes.get("stage", current["stage"]))
        milestone = _milestone(stage)
        status = str(changes.get("status", current["status"]))
        value = {
            **changes, "stage": stage, "percent": changes.get("percent", milestone[0]),
            "progress_kind": "workflow_milestone", "stage_label": milestone[1],
            "stage_index": _stage_index(stage),
            "stage_count": len(ARCHIVE_WORKFLOW_MILESTONES),
            "allowed_actions": ARCHIVE_TASK_ACTIONS[status],
            "updated_at": changes.get("updated_at", utc_now()),
        }
        if "error_summary" in value:
            value["error_summary"] = safe_error(value["error_summary"])
        _validate_milestone({**current, **value})
        if _stage_index(stage) < _stage_index(current["stage"]):
            raise WorkbenchPersistenceError("ARCHIVE_STAGE_REGRESSION")
        if status in {"succeeded", "failed_retryable", "failed_terminal", "cancelled"}:
            value.setdefault("finished_at", value["updated_at"])
            value.setdefault("worker_state", "released")
        return self.tasks.update(task_id, value, expected_revision)

    def get_current_or_recent(self, case_id: str) -> dict[str, Any] | None:
        case_id = validate_opaque_id(case_id)
        placeholders = ",".join("?" for _ in _ACTIVE)
        with self.database.connect() as connection:
            row = connection.execute(
                f"SELECT task_id FROM task_records WHERE case_id=? AND kind='archive' "
                f"AND deployment_instance_id=? AND status IN ({placeholders}) "
                f"ORDER BY updated_at DESC, created_at DESC LIMIT 1",
                (case_id, self.database.deployment_instance_id, *_ACTIVE),
            ).fetchone()
            if row is None:
                row = connection.execute(
                    "SELECT task_id FROM task_records WHERE case_id=? AND kind='archive' "
                    "AND deployment_instance_id=? AND status NOT IN ('queued','running','cancelling','blocked') "
                    "ORDER BY COALESCE(finished_at,updated_at,created_at) DESC LIMIT 1",
                    (case_id, self.database.deployment_instance_id),
                ).fetchone()
        return None if row is None else self.get(str(row[0]))

    def get_history(self, case_id: str) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT task_id FROM task_records WHERE case_id=? AND kind='archive' "
                "AND deployment_instance_id=? ORDER BY created_at DESC, task_id DESC",
                (validate_opaque_id(case_id), self.database.deployment_instance_id),
            ).fetchall()
        return [self.get(str(row[0])) for row in rows]

    def list_queued(self) -> list[dict[str, Any]]:
        """Return the durable queue ordered by priority and creation time."""
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT task_id,counters_json,created_at FROM task_records "
                "WHERE kind='archive' AND deployment_instance_id=? AND status='queued'",
                (self.database.deployment_instance_id,),
            ).fetchall()
        ranked = sorted(
            rows,
            key=lambda row: (
                -float(row_json(row, "counters_json").get("priority", 0)),
                str(row["created_at"]),
                str(row["task_id"]),
            ),
        )
        return [self.get(str(row["task_id"])) for row in ranked]

    def claim(
        self,
        task_id: str,
        *,
        owner_token: str,
        attempt_id: str,
        expected_revision: int,
        max_running: int,
    ) -> dict[str, Any]:
        """Atomically enforce the concurrency cap and bind one queued task."""
        task_id = validate_opaque_id(task_id)
        owner_token = validate_opaque_id(owner_token)
        attempt_id = validate_opaque_id(attempt_id)
        now = utc_now()
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT case_id,status,revision,deployment_instance_id,process_binding_json "
                "FROM task_records WHERE task_id=? AND kind='archive' AND deployment_instance_id=?",
                (task_id, self.database.deployment_instance_id),
            ).fetchone()
            if row is None:
                raise WorkbenchPersistenceError("ARCHIVE_TASK_NOT_FOUND")
            if int(row["revision"]) != expected_revision:
                raise RevisionConflictError(
                    "task", expected_revision, int(row["revision"]),
                )
            if row["status"] != "queued":
                raise WorkbenchPersistenceError("ARCHIVE_TASK_NOT_CLAIMABLE")
            if row["deployment_instance_id"] != self.database.deployment_instance_id:
                raise WorkbenchPersistenceError("ARCHIVE_DEPLOYMENT_MISMATCH")
            running = int(connection.execute(
                "SELECT COUNT(*) FROM task_records WHERE kind='archive' "
                "AND deployment_instance_id=? AND status IN ('running','cancelling')",
                (self.database.deployment_instance_id,),
            ).fetchone()[0])
            if running >= max_running:
                raise WorkbenchPersistenceError("ARCHIVE_CONCURRENCY_LIMIT")
            attempt = connection.execute(
                "SELECT task_id, deployment_instance_id, case_id, status FROM archive_attempts "
                "WHERE attempt_id=? AND deployment_instance_id=?",
                (attempt_id, self.database.deployment_instance_id),
            ).fetchone()
            legacy_binding = None if row["process_binding_json"] is None else row_json(
                row, "process_binding_json",
            )
            if attempt is None and (
                not legacy_binding or legacy_binding.get("staging_asset_id") != attempt_id
            ):
                raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_BINDING_MISMATCH")
            if attempt is not None and (
                attempt["task_id"] != task_id
                or attempt["deployment_instance_id"] != self.database.deployment_instance_id
                or attempt["case_id"] != row["case_id"]
                or attempt["status"] not in {"accepted", "running"}
            ):
                raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_BINDING_MISMATCH")
            updated = connection.execute(
                "UPDATE task_records SET status='running',worker_state='starting',"
                "process_binding_json=?,started_at=COALESCE(started_at,?),updated_at=?,"
                "error_code=NULL,error_summary=NULL,allowed_actions_json=?,revision=revision+1 "
                "WHERE task_id=? AND deployment_instance_id=? AND revision=? AND status='queued'",
                (
                    json_text({
                        "process_tree_id": owner_token,
                        "staging_asset_id": attempt_id,
                    }),
                    now, now, json_text(ARCHIVE_TASK_ACTIONS["running"]),
                    task_id, self.database.deployment_instance_id, expected_revision,
                ),
            )
            if updated.rowcount != 1:
                raise RevisionConflictError(
                    "task", expected_revision, int(row["revision"]),
                )
            # The short context lease only protects an unclaimed queued task.
            # Once this transaction establishes durable running ownership, a
            # long WinRAR execution must not expire the publication binding.
            connection.execute(
                "UPDATE archive_context_bindings SET expires_at=NULL "
                "WHERE attempt_id=? AND active=1",
                (attempt_id,),
            )
        return self.get(task_id)

    def is_owned_by(self, task_id: str, owner_token: str) -> bool:
        task = self.get(task_id)
        binding = task.get("process_binding") or {}
        return (
            task["status"] in {"running", "cancelling"}
            and binding.get("process_tree_id") == validate_opaque_id(owner_token)
        )

    def recover_after_restart(self) -> list[dict[str, Any]]:
        rows = self.list_inflight()
        recovered = []
        for task in rows:
            recovered.append(self.update_state(task["task_id"], {
                "status": "interrupted", "worker_state": "waiting_reclaim",
                "error_code": "ARCHIVE_WAITING_RECLAIM",
                "error_summary": "Archive task is waiting for safe reclaim.",
            }, task["revision"]))
        return recovered

    def list_inflight(self) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT task_id FROM task_records WHERE kind='archive' "
                "AND deployment_instance_id=? AND status IN ('running','cancelling') "
                "ORDER BY created_at,task_id",
                (self.database.deployment_instance_id,),
            ).fetchall()
        return [self.get(str(row[0])) for row in rows]

    def get_card_summary(self, case_id: str) -> dict[str, Any] | None:
        task = self.get_current_or_recent(case_id)
        if task is None:
            return None
        return self.get_task_card_summary(task["task_id"])

    def get_task_card_summary(self, task_id: str) -> dict[str, Any]:
        return build_archive_task_card_summary(self.database, self.get(task_id))
