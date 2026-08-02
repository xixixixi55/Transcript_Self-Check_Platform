"""Atomic cleaned-case tombstone compaction behind a durable cleanup claim."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .cleanup_run_helpers import claim_matches, lease_live, select_run
from .retention_repository_helpers import identifier, required_time
from .workbench_database import WorkbenchDatabase, utc_now_z
from .workbench_errors import RevisionConflictError, WorkbenchPersistenceError
from .workbench_serialization import validate_safe_string

_ACTIVE_TASK_STATUSES = ("queued", "running", "cancelling", "interrupted", "failed_retryable")


class CaseTombstoneRepository:
    """Compact only after the cleanup worker has proven its durable claim."""

    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database

    def compact_cleaned(
        self,
        case_id: str,
        *,
        expected_revision: int,
        cleanup_run_id: str,
        owner_instance_id: str,
        claim_token: str,
        fence_epoch: int,
        policy_revision: int,
        safe_display_summary: str,
        retention_anchor_utc: str,
        now: str | None = None,
    ) -> dict[str, Any]:
        case_id = identifier(case_id)
        cleanup_run_id = identifier(cleanup_run_id)
        owner_instance_id = identifier(owner_instance_id)
        claim_token = identifier(claim_token)
        _revision(expected_revision)
        _revision(fence_epoch, minimum=1)
        _revision(policy_revision, minimum=1)
        summary = validate_safe_string(safe_display_summary, "INVALID_TOMBSTONE")
        if not summary.strip():
            raise WorkbenchPersistenceError("INVALID_TOMBSTONE")
        anchor = required_time(retention_anchor_utc)
        now_value = required_time(now) if now is not None else utc_now_z()

        with self.database.transaction() as connection:
            shell = connection.execute(
                "SELECT * FROM case_shells WHERE case_id=? AND deployment_instance_id=?",
                (case_id, self.database.deployment_instance_id),
            ).fetchone()
            if shell is None:
                raise WorkbenchPersistenceError("CASE_NOT_FOUND")
            if bool(shell["record_cleaned"]):
                raise WorkbenchPersistenceError("CASE_RECORD_CLEANED")
            actual_revision = int(shell["revision"])
            if actual_revision != expected_revision:
                raise RevisionConflictError("case_shell", expected_revision, actual_revision)
            if shell["lifecycle"] != "record_retention_expired":
                raise WorkbenchPersistenceError("CLEANUP_PRECONDITION_FAILED")
            self._assert_claim(
                connection, cleanup_run_id, case_id, owner_instance_id, claim_token,
                fence_epoch, expected_revision, policy_revision, now_value,
            )
            retention_cleanup_revision = self._assert_retention_fact(connection, case_id, shell, policy_revision, anchor)
            self._assert_no_active_work(connection, case_id)
            self._assert_formal_authority(connection, case_id)
            connection.execute("DELETE FROM case_drafts WHERE case_id=?", (case_id,))
            updated = connection.execute(
                "UPDATE case_shells SET case_number=NULL,case_summary=?,source_id=NULL,"
                "parse_task_id=NULL,report_available=0,lifecycle='record_cleaned',revision=revision+1,"
                "updated_at=?,record_cleaned=1,tombstone_revision=tombstone_revision+1,"
                "retention_state='completed',cleanup_state='records_cleaned',cleaned_at=?,"
                "retention_anchor_utc=?,safe_display_summary=?,cleanup_revision=cleanup_revision+1 "
                "WHERE case_id=? AND deployment_instance_id=? AND revision=? AND record_cleaned=0",
                (summary, now_value, now_value, anchor, summary, case_id,
                 self.database.deployment_instance_id, expected_revision),
            )
            if updated.rowcount != 1:
                raise RevisionConflictError("case_shell", expected_revision, actual_revision)
            retention_updated = connection.execute(
                "UPDATE case_retention_records SET eligibility='eligible',status='completed',"
                "last_blocker_code=NULL,retention_anchor_utc=?,policy_revision=?,case_revision=?,"
                "cleanup_revision=cleanup_revision+1,updated_at=? WHERE deployment_instance_id=? AND case_id=? "
                "AND policy_revision=? AND case_revision=? AND cleanup_revision=?",
                (anchor, policy_revision, expected_revision + 1, now_value,
                 self.database.deployment_instance_id, case_id, policy_revision, expected_revision,
                 retention_cleanup_revision),
            )
            if retention_updated.rowcount != 1:
                raise WorkbenchPersistenceError("CLEANUP_STALE_REQUEST")
            run_updated = connection.execute(
                "UPDATE case_cleanup_runs SET current_phase='records_cleaned',updated_at=? "
                "WHERE cleanup_run_id=? AND deployment_instance_id=? AND case_id=? "
                "AND current_phase='work_files_cleaned' AND policy_revision=? "
                "AND case_revision_at_claim=? AND owner_instance_id=? AND claim_token=? AND fence_epoch=?",
                (now_value, cleanup_run_id, self.database.deployment_instance_id, case_id,
                 policy_revision, expected_revision, owner_instance_id, claim_token, fence_epoch),
            )
            if run_updated.rowcount != 1:
                raise WorkbenchPersistenceError("CLEANUP_STALE_REQUEST")
            refreshed = connection.execute(
                "SELECT * FROM case_shells WHERE case_id=? AND deployment_instance_id=?",
                (case_id, self.database.deployment_instance_id),
            ).fetchone()
        return {"case_id": case_id, **shell_tombstone_projection(refreshed)}

    def _assert_claim(
        self, connection: Any, run_id: str, case_id: str, owner: str, token: str,
        fence_epoch: int, case_revision: int, policy_revision: int, now: str,
    ) -> None:
        run = select_run(connection, self.database.deployment_instance_id, run_id)
        if run is None or run["case_id"] != case_id:
            raise WorkbenchPersistenceError("CLEANUP_RUN_NOT_FOUND")
        if not claim_matches(run, "work_files_cleaned", owner, token, fence_epoch, case_revision, policy_revision):
            raise WorkbenchPersistenceError("CLEANUP_STALE_REQUEST")
        if not lease_live(run["lease_expires_at"], now):
            raise WorkbenchPersistenceError("CLEANUP_STALE_REQUEST")
        policy = connection.execute(
            "SELECT policy_revision FROM case_retention_policies WHERE deployment_instance_id=?",
            (self.database.deployment_instance_id,),
        ).fetchone()
        if policy is None or int(policy[0]) != policy_revision:
            raise WorkbenchPersistenceError("CLEANUP_STALE_REQUEST")

    def _assert_retention_fact(
        self, connection: Any, case_id: str, shell: Mapping[str, Any],
        policy_revision: int, anchor: str,
    ) -> int:
        row = connection.execute(
            "SELECT eligibility,status,retention_anchor_utc,policy_revision,case_revision,cleanup_revision "
            "FROM case_retention_records WHERE deployment_instance_id=? AND case_id=?",
            (self.database.deployment_instance_id, case_id),
        ).fetchone()
        if row is None or row["retention_anchor_utc"] is None:
            raise WorkbenchPersistenceError("RETENTION_TIME_INVALID")
        if (
            row["eligibility"] != "eligible" or row["status"] not in {"eligible", "planned", "processing"}
            or int(row["policy_revision"]) != policy_revision
            or int(row["case_revision"]) != int(shell["revision"])
            or int(row["cleanup_revision"]) != int(shell["cleanup_revision"])
        ):
            raise WorkbenchPersistenceError("RETENTION_AUTHORITY_INCONSISTENT")
        try:
            stored_anchor = required_time(row["retention_anchor_utc"])
        except WorkbenchPersistenceError as error:
            raise WorkbenchPersistenceError("RETENTION_TIME_INVALID") from error
        if stored_anchor != anchor:
            raise WorkbenchPersistenceError("RETENTION_AUTHORITY_INCONSISTENT")
        return int(row["cleanup_revision"])

    def _assert_no_active_work(self, connection: Any, case_id: str) -> None:
        if connection.execute(
            "SELECT 1 FROM edit_leases AS leases JOIN case_shells AS shells "
            "ON shells.case_id=leases.case_id WHERE leases.case_id=? "
            "AND shells.deployment_instance_id=? AND leases.status='active' LIMIT 1",
            (case_id, self.database.deployment_instance_id),
        ).fetchone() is not None:
            raise WorkbenchPersistenceError("RETENTION_ACTIVE_LEASE")
        placeholders = ",".join("?" for _ in _ACTIVE_TASK_STATUSES)
        if connection.execute(
            f"SELECT 1 FROM task_records WHERE case_id=? AND deployment_instance_id=? "
            f"AND status IN ({placeholders}) LIMIT 1",
            (case_id, self.database.deployment_instance_id, *_ACTIVE_TASK_STATUSES),
        ).fetchone() is not None:
            raise WorkbenchPersistenceError("RETENTION_ACTIVE_TASK")
        if connection.execute(
            "SELECT 1 FROM archive_publish_fences WHERE case_id=? AND deployment_instance_id=? "
            "AND status IN ('active','pending_verification') LIMIT 1",
            (case_id, self.database.deployment_instance_id),
        ).fetchone() is not None:
            raise WorkbenchPersistenceError("RETENTION_RECOVERY_IN_PROGRESS")

    def _assert_formal_authority(self, connection: Any, case_id: str) -> None:
        publications = connection.execute(
            "SELECT publication_id,phase,publication_status,publication_verified_at "
            "FROM archive_publish_intents WHERE case_id=? AND deployment_instance_id=? "
            "AND publication_id IS NOT NULL",
            (case_id, self.database.deployment_instance_id),
        ).fetchall()
        if not publications:
            raise WorkbenchPersistenceError("RETENTION_PUBLICATION_MISSING")
        if any(
            row["phase"] != "verified" or row["publication_status"] != "verified"
            or row["publication_verified_at"] is None for row in publications
        ):
            raise WorkbenchPersistenceError("RETENTION_PUBLICATION_UNVERIFIED")
        words = connection.execute(
            "SELECT w.status,w.verified_at,p.phase,p.publication_status,p.publication_verified_at "
            "FROM formal_word_artifacts w LEFT JOIN archive_publish_intents p ON "
            "p.publication_id=w.publication_id AND p.deployment_instance_id=w.deployment_instance_id "
            "AND p.case_id=w.case_id WHERE w.case_id=? AND w.deployment_instance_id=?",
            (case_id, self.database.deployment_instance_id),
        ).fetchall()
        if not words:
            raise WorkbenchPersistenceError("RETENTION_WORD_ARTIFACT_MISSING")
        if any(
            row["status"] != "verified" or row["verified_at"] is None
            or row["phase"] != "verified" or row["publication_status"] != "verified"
            or row["publication_verified_at"] is None for row in words
        ):
            raise WorkbenchPersistenceError("RETENTION_WORD_ARTIFACT_UNVERIFIED")


def shell_tombstone_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "record_cleaned": bool(row["record_cleaned"]),
        "tombstone_revision": int(row["tombstone_revision"]),
        "retention_state": row["retention_state"], "cleanup_state": row["cleanup_state"],
        "cleaned_at": row["cleaned_at"],
        "last_meaningful_mutation_at": row["last_meaningful_mutation_at"],
        "retention_anchor_utc": row["retention_anchor_utc"],
        "safe_display_summary": row["safe_display_summary"],
        "cleanup_revision": int(row["cleanup_revision"]),
    }


def _revision(value: Any, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise WorkbenchPersistenceError("INVALID_TOMBSTONE")
    return value
