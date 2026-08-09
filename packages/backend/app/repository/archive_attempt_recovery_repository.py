"""Atomic persistence operations for archive completion and restart recovery."""

from __future__ import annotations

import json
from typing import Any

from .archive_attempt_projection_repository import internal_attempt
from .archive_attempt_evidence_repository import bind_manifest_evidence
from .archive_attempt_lookup_repository import public as _public, row as _row
from .archive_context_binding_repository import deactivate_bindings, report_fingerprint
from .archive_report_metadata_repository import update_verified_draft
from .workbench_database import WorkbenchDatabase, utc_now
from .workbench_errors import WorkbenchPersistenceError
from .workbench_serialization import validate_opaque_id
from .workbench_repository_helpers import json_text
from .workbench_constants import ARCHIVE_TASK_ACTIONS

def list_unfinished(database: WorkbenchDatabase) -> list[dict[str, Any]]:
    connection = database.connect()
    try:
        rows = connection.execute(
            "SELECT * FROM archive_attempts WHERE deployment_instance_id=? "
            "AND status IN ('accepted', 'running') "
            "ORDER BY created_at, attempt_id",
            (database.deployment_instance_id,),
        ).fetchall()
    finally:
        connection.close()
    return [internal_attempt(row) for row in rows]


def complete_attempt(
    database: WorkbenchDatabase, attempt_id: str, manifest_id: str,
) -> dict[str, Any]:
    raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_REQUIRED")


def complete_verified_attempt(
    database: WorkbenchDatabase, evidence: dict[str, Any],
) -> dict[str, Any]:
    """Commit only evidence already verified by the completion service."""
    attempt_id = validate_opaque_id(evidence.get("attempt_id"))
    manifest_id = validate_opaque_id(evidence.get("manifest_id"))
    required = (
        "task_id", "deployment_instance_id", "case_id", "source_id", "source_revision", "draft_revision",
        "report_fingerprint", "source_key", "input_fingerprint", "archive_fingerprint",
        "relative_final_dir", "shell_revision", "publication_id", "publication_digest",
        "publication_file_set", "attachment_projection", "merge_shell_revision",
        "merge_draft_revision", "merge_report_fingerprint",
    )
    if any(key not in evidence for key in required):
        raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_REQUIRED")
    attempt_id = validate_opaque_id(attempt_id)
    now = utc_now()
    with database.transaction() as connection:
        row = connection.execute(
            "SELECT * FROM archive_attempts WHERE attempt_id = ? AND deployment_instance_id=?",
            (attempt_id, database.deployment_instance_id),
        ).fetchone()
        if row is None:
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_NOT_FOUND")
        legacy_attempt = (
            evidence["task_id"] == f"legacy-task-{attempt_id}"
            and row["task_id"] in (None, f"legacy-task-{attempt_id}")
        )
        if (
            (not legacy_attempt and row["task_id"] != evidence["task_id"])
            or row["deployment_instance_id"] != evidence["deployment_instance_id"]
            or row["deployment_instance_id"] != database.deployment_instance_id
        ):
            raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_CONFLICT")
        if row["status"] == "succeeded":
            if row["manifest_id"] != manifest_id:
                raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_CONFLICT")
            return _public(database, attempt_id)
        recovery = bool(evidence.get("recovery"))
        allowed_attempt_statuses = {"accepted", "running"} | ({"interrupted"} if recovery else set())
        if row["status"] not in allowed_attempt_statuses:
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_STATE_INVALID")
        if (
            row["case_id"] != evidence["case_id"] or row["source_id"] != evidence["source_id"]
            or int(row["source_revision"] or row["input_revision"]) != int(evidence["source_revision"])
            or int(row["draft_revision"] or 0) != int(evidence["draft_revision"])
            or row["report_fingerprint"] != evidence["report_fingerprint"]
        ):
            raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_CONFLICT")
        intent = connection.execute(
            "SELECT * FROM archive_publish_intents WHERE attempt_id = ? "
            "AND deployment_instance_id=?",
            (attempt_id, database.deployment_instance_id),
        ).fetchone()
        if intent is None or intent["phase"] not in {"indexed", "verified"}:
            raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_REQUIRED")
        if (
            intent["task_id"] != evidence["task_id"]
            or intent["deployment_instance_id"] != database.deployment_instance_id
            or intent["publication_id"] != evidence["publication_id"]
            or intent["publication_digest"] != evidence["publication_digest"]
            or intent["publication_file_set_json"] != json.dumps(
                evidence["publication_file_set"], ensure_ascii=False,
                sort_keys=True, separators=(",", ":"),
            )
            or intent["publication_status"] not in {"sealed", "published", "verified"}
        ):
            raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_CONFLICT")
        fence = connection.execute(
            "SELECT * FROM archive_publish_fences WHERE fence_id = ? AND attempt_id = ? "
            "AND deployment_instance_id=?",
            (intent["fence_id"], attempt_id, database.deployment_instance_id),
        ).fetchone() if intent["fence_id"] else None
        expected_fence_statuses = {"active"} if not recovery else {"pending_verification"}
        if (
            fence is None or fence["status"] not in expected_fence_statuses
            or fence["case_id"] != evidence["case_id"]
            or fence["source_id"] != evidence["source_id"]
            or int(fence["source_revision"]) != int(evidence["source_revision"])
            or int(fence["draft_revision"]) != int(evidence["draft_revision"])
            or fence["report_fingerprint"] != evidence["report_fingerprint"]
            or int(fence["shell_revision"]) != int(evidence["shell_revision"])
        ):
            raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_CONFLICT")
        if any(intent[key] != evidence[key] for key in (
            "case_id", "source_id", "source_revision", "draft_revision",
            "report_fingerprint", "source_key", "input_fingerprint",
            "archive_fingerprint", "relative_final_dir",
        )) or intent["manifest_id"] != manifest_id:
            raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_CONFLICT")
        shell = connection.execute(
            "SELECT source_id, lifecycle, revision FROM case_shells WHERE case_id = ?",
            (evidence["case_id"],),
        ).fetchone()
        source = connection.execute(
            "SELECT case_id, revision, access_status FROM source_records WHERE source_id = ?",
            (evidence["source_id"],),
        ).fetchone()
        draft = connection.execute(
            "SELECT revision, report_json, lifecycle FROM case_drafts WHERE case_id = ?",
            (evidence["case_id"],),
        ).fetchone()
        task = None if legacy_attempt else connection.execute(
            "SELECT * FROM task_records WHERE task_id=? AND kind='archive' "
            "AND deployment_instance_id=?",
            (evidence["task_id"], database.deployment_instance_id),
        ).fetchone()
        binding_query = (
            "SELECT context_hash, case_id, source_id, source_revision, draft_revision, report_fingerprint, "
            "context_kind, active FROM archive_context_bindings WHERE attempt_id = ? "
            + ("AND active = 1" if not recovery else "")
        )
        binding = connection.execute(binding_query, (attempt_id,)).fetchall()
        allowed_lifecycles = {"archive_queued", "archiving"} if not recovery else {"archive_interrupted"}
        if (
            ((not legacy_attempt) and (
                task is None or task["deployment_instance_id"] != database.deployment_instance_id
                or task["case_id"] != evidence["case_id"]
                or task["status"] not in ({"running", "cancelling", "interrupted", "succeeded"}
                                            if recovery else {"running", "cancelling"})
            ))
            or shell is None or source is None or draft is None or len(binding) != 1
            or shell["source_id"] != evidence["source_id"]
            or shell["lifecycle"] not in allowed_lifecycles
            or source["case_id"] != evidence["case_id"]
            or int(source["revision"]) != int(evidence["source_revision"])
            or source["access_status"] != "available"
            or draft["lifecycle"] not in allowed_lifecycles
            or binding[0]["case_id"] != evidence["case_id"]
            or binding[0]["context_hash"] != fence["context_hash"]
            or binding[0]["source_id"] != evidence["source_id"]
            or int(binding[0]["source_revision"]) != int(evidence["source_revision"])
            or int(binding[0]["draft_revision"]) != int(evidence["draft_revision"])
            or binding[0]["report_fingerprint"] != evidence["report_fingerprint"]
            or binding[0]["context_kind"] != "workbench"
            or (not recovery and not bool(binding[0]["active"]))
        ):
            raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_CONFLICT")
        if (
            int(shell["revision"]) != int(evidence["merge_shell_revision"])
            or int(draft["revision"]) != int(evidence["merge_draft_revision"])
            or report_fingerprint(json.loads(draft["report_json"]))
            != evidence["merge_report_fingerprint"]
        ):
            raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_MERGE_CONFLICT")
        cleanup = "succeeded" if row["staging_locator"] else "not_required"
        attempt_sql = (
            "UPDATE archive_attempts SET status = 'succeeded', manifest_id = ?, "
            "manifest_source_key = ?, manifest_input_fingerprint = ?, manifest_archive_fingerprint = ?, "
            "cleanup_status = ?, error_code = NULL, finished_at = ?, revision = revision + 1 "
            "WHERE attempt_id = ? AND deployment_instance_id=? "
            "AND (task_id IS NULL OR task_id=?)"
            if legacy_attempt else
            "UPDATE archive_attempts SET status = 'succeeded', manifest_id = ?, "
            "manifest_source_key = ?, manifest_input_fingerprint = ?, manifest_archive_fingerprint = ?, "
            "cleanup_status = ?, error_code = NULL, finished_at = ?, revision = revision + 1 "
            "WHERE attempt_id = ? AND task_id = ? AND deployment_instance_id = ?"
        )
        attempt_params = (
            (manifest_id, evidence["source_key"], evidence["input_fingerprint"],
             evidence["archive_fingerprint"], cleanup, now, attempt_id,
             database.deployment_instance_id, f"legacy-task-{attempt_id}")
            if legacy_attempt else
            (manifest_id, evidence["source_key"], evidence["input_fingerprint"],
             evidence["archive_fingerprint"], cleanup, now, attempt_id,
             evidence["task_id"], database.deployment_instance_id)
        )
        updated_attempt = connection.execute(attempt_sql, attempt_params)
        if updated_attempt.rowcount != 1:
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_STATE_INVALID")
        deactivate_bindings(connection, attempt_id)
        updated_shell = connection.execute(
            "UPDATE case_shells SET lifecycle = 'archive_verified', revision = revision + 1, "
            "updated_at = ? WHERE case_id = ? AND source_id = ? AND revision = ? "
            "AND lifecycle IN ('archive_queued', 'archiving', 'archive_interrupted')",
            (now, evidence["case_id"], evidence["source_id"], int(evidence["merge_shell_revision"])),
        )
        if updated_shell.rowcount != 1:
            raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_CONFLICT")
        update_verified_draft(
            connection, draft, intent, evidence["case_id"],
            int(evidence["merge_draft_revision"]), now, evidence["attachment_projection"],
        )
        updated_fence = connection.execute(
            "UPDATE archive_publish_fences SET status = 'consumed', reason = 'ARCHIVE_COMPLETION_VERIFIED', updated_at = ? "
            "WHERE fence_id = ? AND attempt_id=? AND task_id=? AND deployment_instance_id=? "
            "AND status IN ('active', 'pending_verification')",
            (now, fence["fence_id"], attempt_id, evidence["task_id"], database.deployment_instance_id),
        )
        if updated_fence.rowcount != 1:
            raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_FENCE_STATE_INVALID")
        updated_intent = connection.execute(
            "UPDATE archive_publish_intents SET phase='verified', publication_status='verified', "
            "updated_at=? WHERE attempt_id=? AND task_id=? AND deployment_instance_id=? "
            "AND phase IN ('indexed','verified') AND publication_status IN ('sealed','published','verified')",
            (now, attempt_id, evidence["task_id"], database.deployment_instance_id),
        )
        if updated_intent.rowcount != 1:
            raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_INTENT_STATE_INVALID")
        if not legacy_attempt and task["status"] != "succeeded":
            updated_task = connection.execute(
                "UPDATE task_records SET status='succeeded', stage='completed', percent=100, "
                "error_code=NULL, error_summary=NULL, cancel_requested=0, updated_at=?, "
                "finished_at=?, worker_state='released', allowed_actions_json=?, revision=revision+1 "
                "WHERE task_id=? AND deployment_instance_id=? AND status IN ('running','cancelling','interrupted')",
                (now, now, json_text(ARCHIVE_TASK_ACTIONS["succeeded"]),
                 evidence["task_id"], database.deployment_instance_id),
            )
            if updated_task.rowcount != 1:
                raise WorkbenchPersistenceError("ARCHIVE_TASK_STATE_INVALID")
    return _public(database, attempt_id)
