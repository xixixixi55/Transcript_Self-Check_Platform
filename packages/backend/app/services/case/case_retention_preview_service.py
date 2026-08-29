"""确定性无路径保留预览投影。"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from ...repository.retention_policy_repository import RetentionPolicyRepository
from ...repository.workbench_database import WorkbenchDatabase
from ...repository.workbench_errors import WorkbenchPersistenceError
from .case_retention_service import CaseRetentionService

_PLANNED_CATEGORIES = (
    "draft", "work_task", "work_source", "work_asset", "snapshot", "staging", "cache",
)
_PRESERVED_CATEGORIES = (
    "rar", "manifest", "md5", "formal_word", "publication_authority", "case_tombstone",
)
_CONFLICT_CODES = {
    "RETENTION_AUTHORITY_INCONSISTENT", "RETENTION_OWNERSHIP_UNKNOWN",
    "RETENTION_RECOVERY_IN_PROGRESS", "RETENTION_SNAPSHOT_OWNERSHIP_UNKNOWN",
}
_ACTIVE_TASKS = ("queued", "running", "cancelling", "interrupted", "failed_retryable")


class CaseRetentionPreviewService:
    """构建稳定试运行投影，不创建清理运行。"""

    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database
        self.retention = CaseRetentionService(database)

    def preview(self, *, now: datetime | str | None = None) -> dict[str, Any]:
        reference = _reference_time(now)
        policy = RetentionPolicyRepository(self.database).get()
        case_ids = self._case_ids()
        items = [self._item(case_id, policy, reference) for case_id in case_ids]
        digest_input = {
            "policy": {key: policy[key] for key in (
                "mode", "retention_days", "scan_interval_seconds", "batch_size", "policy_revision",
            )},
            "items": [item["digest"] for item in items],
        }
        return {
            "policy": {key: policy[key] for key in (
                "mode", "retention_days", "scan_interval_seconds", "batch_size",
                "policy_revision", "activated_at", "updated_at",
            )},
            "items": items,
            "generated_at": _iso(reference),
            "policy_revision": int(policy["policy_revision"]),
            "preview_digest": _digest(digest_input),
        }

    def _case_ids(self) -> list[str]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT case_id FROM case_shells WHERE deployment_instance_id=? ORDER BY case_id ASC",
                (self.database.deployment_instance_id,),
            ).fetchall()
        return [str(row[0]) for row in rows]

    def _item(self, case_id: str, policy: dict[str, Any], now: datetime) -> dict[str, Any]:
        try:
            result = self.retention.evaluate_case(case_id, now=now)
        except WorkbenchPersistenceError as error:
            result = {
                "case_id": case_id, "eligibility": "unknown", "status": "unknown",
                "last_blocker_code": error.code, "retention_anchor_utc": None,
                "expires_at_utc": None, "case_revision": 0,
            }
        summary = self._summaries(case_id)
        blocker = result.get("last_blocker_code")
        state = "candidate" if result.get("eligibility") == "eligible" else (
            "skipped" if blocker == "RETENTION_NOT_EXPIRED" else "blocked"
        )
        safe = {
            "case_id": case_id, "state": state, "eligibility": result.get("eligibility", "unknown"),
            "blocker_code": blocker, "planned_data_categories": list(_PLANNED_CATEGORIES),
            "preserved_formal_artifact_categories": list(_PRESERVED_CATEGORIES),
            "retention_anchor_utc": result.get("retention_anchor_utc"),
            "expires_at_utc": result.get("expires_at_utc"),
            "has_running_task": summary["has_running_task"],
            "has_edit_lease": summary["has_edit_lease"],
            "has_recovery": summary["has_recovery"],
            "has_conflict": summary["has_conflict"] or blocker in _CONFLICT_CODES,
            "policy_revision": int(policy["policy_revision"]),
            "case_revision": int(result.get("case_revision", 0)),
        }
        return {**safe, "digest": _digest(safe)}

    def _summaries(self, case_id: str) -> dict[str, bool]:
        with self.database.connect() as connection:
            task_placeholders = ",".join("?" for _ in _ACTIVE_TASKS)
            has_task = connection.execute(
                f"SELECT 1 FROM task_records WHERE case_id=? AND deployment_instance_id=? "
                f"AND status IN ({task_placeholders}) LIMIT 1",
                (case_id, self.database.deployment_instance_id, *_ACTIVE_TASKS),
            ).fetchone() is not None
            has_lease = connection.execute(
                "SELECT 1 FROM edit_leases WHERE case_id=? AND status='active' LIMIT 1", (case_id,),
            ).fetchone() is not None
            has_recovery = any((
                connection.execute(
                    "SELECT 1 FROM archive_publish_fences WHERE case_id=? AND deployment_instance_id=? "
                    "AND status IN ('active','pending_verification') LIMIT 1",
                    (case_id, self.database.deployment_instance_id),
                ).fetchone() is not None,
                connection.execute(
                    "SELECT 1 FROM archive_context_bindings WHERE case_id=? AND active=1 LIMIT 1",
                    (case_id,),
                ).fetchone() is not None,
                connection.execute(
                    "SELECT 1 FROM archive_attempts WHERE case_id=? AND deployment_instance_id=? "
                    "AND (status IN ('accepted','running','interrupted') OR cleanup_status IN ('pending','unknown')) LIMIT 1",
                    (case_id, self.database.deployment_instance_id),
                ).fetchone() is not None,
                connection.execute(
                    "SELECT 1 FROM archive_input_snapshots WHERE case_id=? AND deployment_instance_id=? "
                    "AND status!='cleaned' LIMIT 1",
                    (case_id, self.database.deployment_instance_id),
                ).fetchone() is not None,
                connection.execute(
                    "SELECT 1 FROM case_cleanup_runs WHERE case_id=? AND deployment_instance_id=? "
                    "AND current_phase NOT IN ('succeeded','cancelled','blocked','stale','failed_terminal') LIMIT 1",
                    (case_id, self.database.deployment_instance_id),
                ).fetchone() is not None,
            ))
        return {
            "has_running_task": has_task, "has_edit_lease": has_lease,
            "has_recovery": has_recovery, "has_conflict": has_task or has_lease or has_recovery,
        }


def _reference_time(value: datetime | str | None) -> datetime:
    try:
        parsed = datetime.now(timezone.utc) if value is None else (
            datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
        )
    except (TypeError, ValueError) as error:
        raise WorkbenchPersistenceError("RETENTION_TIME_INVALID") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise WorkbenchPersistenceError("RETENTION_TIME_INVALID")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
