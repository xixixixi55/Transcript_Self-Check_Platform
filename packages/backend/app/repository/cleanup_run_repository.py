"""Durable cleanup-run claim foundation; it never deletes records or files."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .cleanup_run_helpers import (
    ACTIVE_PHASES, PHASES, RECOVERY_PHASES, TERMINAL_PHASES, UNSET, claim_matches,
    claimable, current_time, lease_live, optional_identifier, optional_revision,
    optional_text, preserved_text, public_status, revision, run_dict, same_claim, select_run,
    current_revisions_match,
)
from .retention_repository_helpers import identifier, optional_time, required_time
from .workbench_database import WorkbenchDatabase, utc_now_z
from .workbench_errors import WorkbenchPersistenceError


class CleanupRunRepository:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database

    def create_planned(self, value: Mapping[str, Any]) -> dict[str, Any]:
        run_id = identifier(value.get("cleanup_run_id"))
        case_id = identifier(value.get("case_id"))
        phase = value.get("current_phase", "planned")
        if phase not in PHASES:
            raise WorkbenchPersistenceError("INVALID_CLEANUP_RUN")
        now = utc_now_z()
        fields = (
            run_id, self.database.deployment_instance_id, case_id,
            revision(value.get("policy_revision", 1), minimum=1),
            revision(value.get("case_revision_at_plan", 0)),
            optional_revision(value.get("case_revision_at_claim")),
            optional_identifier(value.get("owner_instance_id")),
            optional_identifier(value.get("claim_token")), optional_time(value.get("lease_expires_at")),
            optional_revision(value.get("fence_epoch")), phase,
            revision(value.get("retry_count", 0)),
            optional_text(value.get("file_step_result")), optional_text(value.get("result_code")),
            optional_text(value.get("error_code")),
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
        expected_policy_revision: int | None = None, now: str | None = None,
    ) -> dict[str, Any]:
        run_id = identifier(run_id)
        owner_instance_id = identifier(owner_instance_id)
        claim_token = identifier(claim_token)
        lease_expires_at = required_time(lease_expires_at)
        expected_case_revision = revision(expected_case_revision)
        now_value = current_time(now)
        if not lease_live(lease_expires_at, now_value):
            raise WorkbenchPersistenceError("CLEANUP_STALE_REQUEST")
        with self.database.transaction() as connection:
            row = select_run(connection, self.database.deployment_instance_id, run_id)
            if row is None:
                raise WorkbenchPersistenceError("CLEANUP_RUN_NOT_FOUND")
            if int(row["case_revision_at_plan"]) != expected_case_revision:
                raise WorkbenchPersistenceError("CLEANUP_STALE_REQUEST")
            policy_revision = revision(row["policy_revision"], minimum=1)
            if expected_policy_revision is not None and (
                revision(expected_policy_revision, minimum=1) != policy_revision
            ):
                raise WorkbenchPersistenceError("CLEANUP_STALE_REQUEST")
            if not current_revisions_match(
                connection, self.database.deployment_instance_id, str(row["case_id"]),
                policy_revision, expected_case_revision,
            ):
                raise WorkbenchPersistenceError("CLEANUP_STALE_REQUEST")
            if row["case_revision_at_claim"] is not None and int(row["case_revision_at_claim"]) != expected_case_revision:
                raise WorkbenchPersistenceError("CLEANUP_STALE_REQUEST")
            if same_claim(row, owner_instance_id, claim_token) and lease_live(row["lease_expires_at"], now_value):
                return run_dict(row)
            if not claimable(row, now_value):
                if lease_live(row["lease_expires_at"], now_value) and row["owner_instance_id"] is not None:
                    raise WorkbenchPersistenceError("CLEANUP_CONFLICT")
                raise WorkbenchPersistenceError("CLEANUP_STALE_REQUEST")
            old_phase = str(row["current_phase"])
            next_phase = "claimed" if old_phase in RECOVERY_PHASES or old_phase == "planned" else old_phase
            next_fence = (optional_revision(row["fence_epoch"]) or 0) + 1
            updated = connection.execute(
                "UPDATE case_cleanup_runs SET current_phase=?,owner_instance_id=?,claim_token=?,"
                "lease_expires_at=?,case_revision_at_claim=?,fence_epoch=?,updated_at=? "
                "WHERE cleanup_run_id=? AND deployment_instance_id=? AND current_phase=? "
                "AND policy_revision=? AND case_revision_at_plan=? AND fence_epoch IS ? "
                "AND owner_instance_id IS ? AND claim_token IS ? AND lease_expires_at IS ?",
                (next_phase, owner_instance_id, claim_token, lease_expires_at, expected_case_revision,
                 next_fence, now_value, run_id, self.database.deployment_instance_id, old_phase, policy_revision,
                 expected_case_revision, row["fence_epoch"], row["owner_instance_id"],
                 row["claim_token"], row["lease_expires_at"]),
            )
            if updated.rowcount != 1:
                raise WorkbenchPersistenceError("CLEANUP_STALE_REQUEST")
        return self.get_internal(run_id)

    def transition(
        self, run_id: str, *, from_phase: str, to_phase: str,
        owner_instance_id: str, claim_token: str, expected_fence_epoch: int,
        expected_case_revision: int, expected_policy_revision: int | None = None,
        file_step_result: Any = UNSET, result_code: Any = UNSET,
        error_code: Any = UNSET, retry_count: int | None = None,
        now: str | None = None,
    ) -> dict[str, Any]:
        if from_phase not in ACTIVE_PHASES or to_phase not in PHASES or to_phase == "planned":
            raise WorkbenchPersistenceError("INVALID_CLEANUP_RUN")
        run_id = identifier(run_id)
        owner_instance_id = identifier(owner_instance_id)
        claim_token = identifier(claim_token)
        expected_fence_epoch = revision(expected_fence_epoch, minimum=1)
        expected_case_revision = revision(expected_case_revision)
        retry_value = None if retry_count is None else revision(retry_count)
        now_value = current_time(now)
        with self.database.transaction() as connection:
            row = select_run(connection, self.database.deployment_instance_id, run_id)
            if row is None:
                raise WorkbenchPersistenceError("CLEANUP_RUN_NOT_FOUND")
            policy_revision = revision(row["policy_revision"], minimum=1)
            if expected_policy_revision is not None:
                expected_policy_revision = revision(expected_policy_revision, minimum=1)
            else:
                expected_policy_revision = policy_revision
            if not claim_matches(
                row, from_phase, owner_instance_id, claim_token, expected_fence_epoch,
                expected_case_revision, expected_policy_revision,
            ):
                raise WorkbenchPersistenceError("CLEANUP_STALE_REQUEST")
            fields = (
                to_phase, int(row["retry_count"]) if retry_value is None else retry_value,
                preserved_text(row["file_step_result"], file_step_result),
                preserved_text(row["result_code"], result_code),
                preserved_text(row["error_code"], error_code), now_value,
                now_value if to_phase in TERMINAL_PHASES else row["completed_at"],
                run_id, self.database.deployment_instance_id, from_phase, policy_revision,
                expected_case_revision, owner_instance_id, claim_token, expected_fence_epoch,
            )
            updated = connection.execute(
                "UPDATE case_cleanup_runs SET current_phase=?,retry_count=?,file_step_result=?,"
                "result_code=?,error_code=?,updated_at=?,completed_at=? WHERE cleanup_run_id=? "
                "AND deployment_instance_id=? AND current_phase=? AND policy_revision=? "
                "AND case_revision_at_claim=? AND owner_instance_id=? AND claim_token=? AND fence_epoch=?",
                fields,
            )
            if updated.rowcount != 1:
                raise WorkbenchPersistenceError("CLEANUP_STALE_REQUEST")
        return self.get_internal(run_id)

    def renew_lease(
        self, run_id: str, *, owner_instance_id: str, claim_token: str,
        expected_fence_epoch: int, expected_case_revision: int,
        lease_expires_at: str, expected_policy_revision: int | None = None,
        now: str | None = None,
    ) -> dict[str, Any]:
        run_id = identifier(run_id)
        owner_instance_id = identifier(owner_instance_id)
        claim_token = identifier(claim_token)
        expected_fence_epoch = revision(expected_fence_epoch, minimum=1)
        expected_case_revision = revision(expected_case_revision)
        lease_expires_at = required_time(lease_expires_at)
        now_value = current_time(now)
        if not lease_live(lease_expires_at, now_value):
            raise WorkbenchPersistenceError("CLEANUP_STALE_REQUEST")
        with self.database.transaction() as connection:
            row = select_run(connection, self.database.deployment_instance_id, run_id)
            if row is None:
                raise WorkbenchPersistenceError("CLEANUP_RUN_NOT_FOUND")
            policy_revision = revision(row["policy_revision"], minimum=1)
            if expected_policy_revision is not None and (
                revision(expected_policy_revision, minimum=1) != policy_revision
            ):
                raise WorkbenchPersistenceError("CLEANUP_STALE_REQUEST")
            if not claim_matches(
                row, str(row["current_phase"]), owner_instance_id, claim_token,
                expected_fence_epoch, expected_case_revision, policy_revision,
            ) or not lease_live(row["lease_expires_at"], now_value):
                raise WorkbenchPersistenceError("CLEANUP_STALE_REQUEST")
            updated = connection.execute(
                "UPDATE case_cleanup_runs SET lease_expires_at=?,updated_at=? WHERE cleanup_run_id=? "
                "AND deployment_instance_id=? AND current_phase IN "
                "('claimed','preflighted','work_files_cleaned','records_cleaned','verified',"
                "'cancel_requested','interrupted','partial_failure','failed_retryable') "
                "AND policy_revision=? AND case_revision_at_claim=? AND owner_instance_id=? "
                "AND claim_token=? AND fence_epoch=? AND lease_expires_at=?",
                (lease_expires_at, now_value, run_id, self.database.deployment_instance_id,
                 policy_revision, expected_case_revision, owner_instance_id, claim_token,
                 expected_fence_epoch, row["lease_expires_at"]),
            )
            if updated.rowcount != 1:
                raise WorkbenchPersistenceError("CLEANUP_STALE_REQUEST")
        return self.get_internal(run_id)

    def list_recoverable(self) -> list[dict[str, Any]]:
        phases = tuple(sorted(ACTIVE_PHASES))
        placeholders = ",".join("?" for _ in phases)
        with self.database.connect() as connection:
            rows = connection.execute(
                f"SELECT cleanup_run_id FROM case_cleanup_runs WHERE deployment_instance_id=? "
                f"AND current_phase IN ({placeholders}) ORDER BY updated_at,cleanup_run_id",
                (self.database.deployment_instance_id, *phases),
            ).fetchall()
        return [self.get_internal(str(row[0])) for row in rows]

    def get_internal(self, run_id: str) -> dict[str, Any]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM case_cleanup_runs WHERE cleanup_run_id=? AND deployment_instance_id=?",
                (identifier(run_id), self.database.deployment_instance_id),
            ).fetchone()
        if row is None:
            raise WorkbenchPersistenceError("CLEANUP_RUN_NOT_FOUND")
        return run_dict(row)

    def get_public(self, run_id: str) -> dict[str, Any]:
        value = self.get_internal(run_id)
        return {
            "run_id": value["cleanup_run_id"], "case_id": value["case_id"],
            "phase": value["current_phase"], "status": public_status(value["current_phase"]),
            "result_code": value["result_code"], "error_code": value["error_code"],
            "updated_at": value["updated_at"], "completed_at": value["completed_at"],
        }
