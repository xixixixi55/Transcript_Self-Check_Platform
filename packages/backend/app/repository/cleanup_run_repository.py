"""Durable cleanup-run claim foundation; it never deletes records or files."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .retention_repository_helpers import identifier, optional_time, required_time, text
from .workbench_database import WorkbenchDatabase, utc_now_z
from .workbench_errors import WorkbenchPersistenceError

_PHASES = {
    "planned", "claimed", "preflighted", "work_files_cleaned", "records_cleaned", "verified",
    "succeeded", "blocked", "stale", "cancel_requested", "cancelled", "interrupted",
    "partial_failure", "failed_retryable", "failed_terminal",
}
_PUBLIC_PHASES = _PHASES


class CleanupRunRepository:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database

    def create_planned(self, value: Mapping[str, Any]) -> dict[str, Any]:
        run_id = identifier(value.get("cleanup_run_id"))
        case_id = identifier(value.get("case_id"))
        phase = value.get("current_phase", "planned")
        if phase not in _PHASES:
            raise WorkbenchPersistenceError("INVALID_CLEANUP_RUN")
        now = utc_now_z()
        fields = (
            run_id, self.database.deployment_instance_id, case_id,
            int(value.get("policy_revision", 1)), int(value.get("case_revision_at_plan", 0)),
            value.get("case_revision_at_claim"), value.get("owner_instance_id"),
            value.get("claim_token"), optional_time(value.get("lease_expires_at")),
            value.get("fence_epoch"), phase, int(value.get("retry_count", 0)),
            value.get("file_step_result"), value.get("result_code"), value.get("error_code"),
            required_time(value.get("created_at", now)), required_time(value.get("updated_at", now)),
            optional_time(value.get("completed_at")),
        )
        with self.database.transaction() as connection:
            try:
                connection.execute(
                    "INSERT INTO case_cleanup_runs(cleanup_run_id,deployment_instance_id,case_id,"
                    "policy_revision,case_revision_at_plan,case_revision_at_claim,owner_instance_id,claim_token,"
                    "lease_expires_at,fence_epoch,current_phase,retry_count,file_step_result,result_code,error_code,"
                    "created_at,updated_at,completed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    fields,
                )
            except Exception as error:
                raise WorkbenchPersistenceError("CLEANUP_RUN_CREATE_FAILED") from error
        return self.get_internal(run_id)

    def claim(
        self, run_id: str, *, owner_instance_id: str, claim_token: str,
        lease_expires_at: str, expected_case_revision: int,
    ) -> dict[str, Any]:
        run_id = identifier(run_id)
        owner_instance_id = identifier(owner_instance_id)
        claim_token = identifier(claim_token)
        lease_expires_at = required_time(lease_expires_at)
        with self.database.transaction() as connection:
            updated = connection.execute(
                "UPDATE case_cleanup_runs SET current_phase='claimed',owner_instance_id=?,claim_token=?,"
                "lease_expires_at=?,case_revision_at_claim=?,updated_at=? WHERE cleanup_run_id=? "
                "AND deployment_instance_id=? AND current_phase='planned' AND case_revision_at_plan=?",
                (owner_instance_id, claim_token, lease_expires_at, expected_case_revision,
                 utc_now_z(), run_id, self.database.deployment_instance_id, expected_case_revision),
            )
            if updated.rowcount != 1:
                raise WorkbenchPersistenceError("CLEANUP_STALE_REQUEST")
        return self.get_internal(run_id)

    def get_internal(self, run_id: str) -> dict[str, Any]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM case_cleanup_runs WHERE cleanup_run_id=? AND deployment_instance_id=?",
                (identifier(run_id), self.database.deployment_instance_id),
            ).fetchone()
        if row is None:
            raise WorkbenchPersistenceError("CLEANUP_RUN_NOT_FOUND")
        return _run_dict(row)

    def get_public(self, run_id: str) -> dict[str, Any]:
        value = self.get_internal(run_id)
        return {
            "run_id": value["cleanup_run_id"], "case_id": value["case_id"],
            "phase": value["current_phase"], "status": _public_status(value["current_phase"]),
            "result_code": value["result_code"], "error_code": value["error_code"],
            "updated_at": value["updated_at"], "completed_at": value["completed_at"],
        }


def _run_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(row)
    for key in ("policy_revision", "case_revision_at_plan", "retry_count"):
        result[key] = int(result[key])
    if result["case_revision_at_claim"] is not None:
        result["case_revision_at_claim"] = int(result["case_revision_at_claim"])
    return result


def _public_status(phase: str) -> str:
    if phase == "succeeded":
        return "succeeded"
    if phase in {"cancelled"}:
        return "cancelled"
    if phase in {"blocked", "stale"}:
        return "blocked"
    if phase in {"partial_failure", "failed_retryable", "failed_terminal"}:
        return "failed"
    return "active"
