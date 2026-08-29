"""持久清理运行的验证、阶段和 CAS 辅助函数。"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from .retention_repository_helpers import identifier, required_time, text
from ..workbench.workbench_database import utc_now_z
from ..workbench.workbench_errors import WorkbenchPersistenceError

PHASES = {
    "planned", "claimed", "preflighted", "work_files_cleaned", "records_cleaned", "verified",
    "succeeded", "blocked", "stale", "cancel_requested", "cancelled", "interrupted",
    "partial_failure", "failed_retryable", "failed_terminal",
}
ACTIVE_PHASES = {
    "planned", "claimed", "preflighted", "work_files_cleaned", "records_cleaned", "verified",
    "cancel_requested", "interrupted", "partial_failure", "failed_retryable",
}
RECOVERY_PHASES = {"interrupted", "partial_failure", "failed_retryable", "cancel_requested"}
TERMINAL_PHASES = {"succeeded", "blocked", "stale", "cancelled", "failed_terminal"}
UNSET = object()


def run_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(row)
    for key in ("policy_revision", "case_revision_at_plan", "retry_count"):
        result[key] = int(result[key])
    if result["case_revision_at_claim"] is not None:
        result["case_revision_at_claim"] = int(result["case_revision_at_claim"])
    if result["fence_epoch"] is not None:
        result["fence_epoch"] = int(result["fence_epoch"])
    return result


def public_status(phase: str) -> str:
    if phase == "succeeded":
        return "succeeded"
    if phase == "cancelled":
        return "cancelled"
    if phase in {"blocked", "stale"}:
        return "blocked"
    if phase in {"partial_failure", "failed_retryable", "failed_terminal"}:
        return "failed"
    return "active"


def select_run(connection: Any, deployment_instance_id: str, run_id: str) -> Any:
    return connection.execute(
        "SELECT * FROM case_cleanup_runs WHERE cleanup_run_id=? AND deployment_instance_id=?",
        (run_id, deployment_instance_id),
    ).fetchone()


def current_revisions_match(
    connection: Any, deployment_instance_id: str, case_id: str,
    policy_revision: int, case_revision: int,
) -> bool:
    policy = connection.execute(
        "SELECT policy_revision FROM case_retention_policies WHERE deployment_instance_id=?",
        (deployment_instance_id,),
    ).fetchone()
    shell = connection.execute(
        "SELECT revision FROM case_shells WHERE case_id=? AND deployment_instance_id=?",
        (case_id, deployment_instance_id),
    ).fetchone()
    return (
        policy is not None and shell is not None
        and int(policy["policy_revision"]) == policy_revision
        and int(shell["revision"]) == case_revision
    )


def revision(value: Any, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise WorkbenchPersistenceError("INVALID_CLEANUP_RUN")
    return value


def optional_revision(value: Any) -> int | None:
    return None if value is None else revision(value)


def optional_identifier(value: Any) -> str | None:
    return None if value is None else identifier(value)


def optional_text(value: Any) -> str | None:
    return None if value is None else text(value, "INVALID_CLEANUP_RUN")


def preserved_text(current: Any, value: Any) -> str | None:
    return optional_text(current if value is UNSET else value)


def current_time(value: str | None) -> str:
    return utc_now_z() if value is None else required_time(value)


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def lease_live(lease_expires_at: Any, current: str) -> bool:
    return lease_expires_at is not None and parse_time(str(lease_expires_at)) > parse_time(current)


def same_claim(row: Mapping[str, Any], owner_instance_id: str, claim_token: str) -> bool:
    return row["owner_instance_id"] == owner_instance_id and row["claim_token"] == claim_token


def claimable(row: Mapping[str, Any], current: str) -> bool:
    phase = str(row["current_phase"])
    if phase not in ACTIVE_PHASES:
        return False
    if row["owner_instance_id"] is None and row["claim_token"] is None:
        return phase == "planned" or phase in RECOVERY_PHASES
    return lease_expired(row["lease_expires_at"], current)


def lease_expired(lease_expires_at: Any, current: str) -> bool:
    return lease_expires_at is not None and not lease_live(lease_expires_at, current)


def claim_matches(
    row: Mapping[str, Any], phase: str, owner_instance_id: str, claim_token: str,
    fence_epoch: int, case_revision: int, policy_revision: int,
) -> bool:
    return (
        row["current_phase"] == phase
        and row["owner_instance_id"] == owner_instance_id
        and row["claim_token"] == claim_token
        and row["fence_epoch"] == fence_epoch
        and row["case_revision_at_claim"] == case_revision
        and row["case_revision_at_plan"] == case_revision
        and row["policy_revision"] == policy_revision
    )
