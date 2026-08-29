"""归档任务状态、选择、重启投影及安全卡片摘要。"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from ..task_record_repository import TaskRecordRepository
from ..workbench_constants import ARCHIVE_TASK_ACTIONS, ARCHIVE_WORKFLOW_MILESTONES
from ..workbench_database import WorkbenchDatabase, utc_now
from ..workbench_errors import RevisionConflictError, WorkbenchPersistenceError
from ..workbench_repository_helpers import json_text, row_json
from ..workbench_serialization import validate_opaque_id

_ACTIVE = ("queued", "running", "cancelling", "blocked")
_ERROR_STATES = {"interrupted", "failed_retryable", "failed_terminal", "cancelled", "blocked"}
_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|/(?:Users|home|tmp|var|etc|opt)/)[^\s,;)]*", re.I)
_TRACE = re.compile(r"^\s*(?:at\s|traceback|file\s+\".*\",\s+line\s+\d+)", re.I)


def _milestone(stage: str) -> tuple[int, str]:
    try:
        return ARCHIVE_WORKFLOW_MILESTONES[stage]
    except KeyError as error:
        raise WorkbenchPersistenceError("INVALID_ARCHIVE_STAGE") from error


def _stage_index(stage: str) -> int:
    return list(ARCHIVE_WORKFLOW_MILESTONES).index(stage) + 1


def _validate_milestone(task: Mapping[str, Any]) -> None:
    if task.get("progress_kind") != "workflow_milestone":
        raise WorkbenchPersistenceError("INVALID_TASK_PROGRESS")
    if task.get("percent") != _milestone(str(task.get("stage")))[0]:
        raise WorkbenchPersistenceError("INVALID_TASK_PROGRESS")


def bind_archive_task_attempt(
    database: WorkbenchDatabase, task_id: str, attempt_id: str,
) -> None:
    task_id = validate_opaque_id(task_id)
    attempt_id = validate_opaque_id(attempt_id)
    now = utc_now()
    with database.transaction() as connection:
        task = connection.execute(
            "SELECT case_id, status, deployment_instance_id, process_binding_json "
            "FROM task_records WHERE task_id=? AND kind='archive'", (task_id,),
        ).fetchone()
        attempt = connection.execute(
            "SELECT task_id, case_id, deployment_instance_id, status "
            "FROM archive_attempts WHERE attempt_id=? AND deployment_instance_id=?",
            (attempt_id, database.deployment_instance_id),
        ).fetchone()
        if task is None or attempt is None:
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_BINDING_MISMATCH")
        if task["deployment_instance_id"] != database.deployment_instance_id:
            raise WorkbenchPersistenceError("ARCHIVE_DEPLOYMENT_MISMATCH")
        if task["status"] != "queued" or task["case_id"] != attempt["case_id"]:
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_BINDING_MISMATCH")
        if attempt["deployment_instance_id"] not in (None, database.deployment_instance_id):
            raise WorkbenchPersistenceError("ARCHIVE_DEPLOYMENT_MISMATCH")
        if attempt["status"] not in {"accepted", "running"}:
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_BINDING_MISMATCH")
        if attempt["task_id"] not in (None, task_id):
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_ALREADY_BOUND")
        if task["process_binding_json"] is not None:
            current_binding = row_json(task, "process_binding_json")
            if current_binding.get("staging_asset_id") == attempt_id:
                return
            raise WorkbenchPersistenceError("ARCHIVE_TASK_ALREADY_BOUND")
        if attempt["task_id"] is None and connection.execute(
            "UPDATE archive_attempts SET task_id=?, deployment_instance_id=?, "
            "revision=revision+1 WHERE attempt_id=? AND task_id IS NULL "
            "AND (deployment_instance_id IS NULL OR deployment_instance_id=?)",
            (task_id, database.deployment_instance_id, attempt_id,
             database.deployment_instance_id),
        ).rowcount != 1:
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_ALREADY_BOUND")
        if connection.execute(
            "UPDATE task_records SET process_binding_json=?, updated_at=?, "
            "revision=revision+1 WHERE task_id=? AND kind='archive' "
            "AND deployment_instance_id=? AND status='queued' "
            "AND process_binding_json IS NULL",
            (json_text({"staging_asset_id": attempt_id}), now, task_id,
             database.deployment_instance_id),
        ).rowcount != 1:
            raise WorkbenchPersistenceError("ARCHIVE_TASK_ALREADY_BOUND")


def build_archive_task_card_summary(
    database: WorkbenchDatabase, task: Mapping[str, Any],
) -> dict[str, Any]:
    summary = {
        key: task[key] for key in (
            "task_id", "case_id", "status", "progress_kind", "stage", "stage_label",
            "stage_index", "stage_count", "percent", "started_at", "updated_at",
            "finished_at", "last_heartbeat_at", "output_bytes", "output_volume_count",
            "last_output_change_at", "worker_state", "allowed_actions",
        )
    }
    summary["error_summary"] = (
        safe_error(task.get("error_summary")) if task["status"] in _ERROR_STATES else None
    )
    if task["status"] == "succeeded" and not _has_verified_manifest(database, task):
        stage_index = list(ARCHIVE_WORKFLOW_MILESTONES).index("manifest") + 1
        summary.update({
            "status": "interrupted",
            "stage": "manifest",
            "stage_label": ARCHIVE_WORKFLOW_MILESTONES["manifest"][1],
            "stage_index": stage_index,
            "percent": ARCHIVE_WORKFLOW_MILESTONES["manifest"][0],
            "worker_state": "released",
            "allowed_actions": ["view_details"],
            "error_summary": "归档结果尚未通过 Manifest 验证。",
        })
    return summary


def _has_verified_manifest(
    database: WorkbenchDatabase, task: Mapping[str, Any],
) -> bool:
    attempt_id = (task.get("process_binding") or {}).get("staging_asset_id")
    if not attempt_id:
        return False
    with database.connect() as connection:
        row = connection.execute(
            "SELECT status,manifest_id FROM archive_attempts WHERE attempt_id=?",
            (attempt_id,),
        ).fetchone()
    return bool(row and row["status"] == "succeeded" and row["manifest_id"])


def safe_error(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    lines = [line for line in value.splitlines() if not _TRACE.search(line)]
    compact = re.sub(
        r"\s+", " ", _PATH.sub("[local path redacted]", " ".join(lines)),
    ).strip()
    return compact if len(compact) <= 160 else f"{compact[:159]}\u2026"


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
        """返回按优先级和创建时间排序的持久队列。"""
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
        """以原子方式实施并发上限并绑定一个排队任务。"""
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
            # 短期上下文租约只保护尚未认领的排队任务。
            # 此事务建立持久运行所有权后，长时间运行的 WinRAR
            # 不得导致发布绑定过期。
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
