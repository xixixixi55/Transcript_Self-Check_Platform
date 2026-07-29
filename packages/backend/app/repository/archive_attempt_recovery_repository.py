"""Atomic persistence operations for archive completion and restart recovery."""

from __future__ import annotations

import json
import re
from typing import Any

from .archive_attempt_projection_repository import internal_attempt, public_attempt
from .archive_context_binding_repository import deactivate_bindings, report_fingerprint
from .workbench_database import WorkbenchDatabase, utc_now
from .workbench_errors import WorkbenchPersistenceError
from .workbench_serialization import validate_opaque_id

_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")


def bind_manifest_evidence(
    database: WorkbenchDatabase,
    attempt_id: str,
    manifest_id: str,
    source_key: str,
    input_fingerprint: str,
    archive_fingerprint: str,
) -> None:
    values = (source_key, input_fingerprint, archive_fingerprint)
    if not all(isinstance(value, str) and _FINGERPRINT.fullmatch(value) for value in values):
        raise WorkbenchPersistenceError("INVALID_ARCHIVE_COMPLETION_EVIDENCE")
    with database.transaction() as connection:
        updated = connection.execute(
            "UPDATE archive_attempts SET manifest_id = ?, manifest_source_key = ?, "
            "manifest_input_fingerprint = ?, manifest_archive_fingerprint = ?, "
            "revision = revision + 1 WHERE attempt_id = ? AND status IN ('accepted', 'running')",
            (
                validate_opaque_id(manifest_id), *values,
                validate_opaque_id(attempt_id),
            ),
        )
        if updated.rowcount != 1:
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_STATE_INVALID")


def list_unfinished(database: WorkbenchDatabase) -> list[dict[str, Any]]:
    connection = database.connect()
    try:
        rows = connection.execute(
            "SELECT * FROM archive_attempts WHERE status IN ('accepted', 'running') "
            "ORDER BY created_at, attempt_id",
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
        "case_id", "source_id", "source_revision", "draft_revision",
        "report_fingerprint", "source_key", "input_fingerprint", "archive_fingerprint",
        "relative_final_dir", "shell_revision",
    )
    if any(key not in evidence for key in required):
        raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_REQUIRED")
    attempt_id = validate_opaque_id(attempt_id)
    now = utc_now()
    with database.transaction() as connection:
        row = connection.execute(
            "SELECT * FROM archive_attempts WHERE attempt_id = ?",
            (attempt_id,),
        ).fetchone()
        if row is None:
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_NOT_FOUND")
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
            "SELECT * FROM archive_publish_intents WHERE attempt_id = ?", (attempt_id,),
        ).fetchone()
        if intent is None or intent["phase"] not in {"indexed", "verified"}:
            raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_REQUIRED")
        fence = connection.execute(
            "SELECT * FROM archive_publish_fences WHERE fence_id = ? AND attempt_id = ?",
            (intent["fence_id"], attempt_id),
        ).fetchone() if intent["fence_id"] else None
        expected_fence_statuses = {"active"} if not recovery else {"pending_verification"}
        if (
            fence is None or fence["status"] not in expected_fence_statuses
            or fence["case_id"] != evidence["case_id"]
            or fence["source_id"] != evidence["source_id"]
            or int(fence["source_revision"]) != int(evidence["source_revision"])
            or int(fence["draft_revision"]) != int(evidence["draft_revision"])
            or fence["report_fingerprint"] != evidence["report_fingerprint"]
            or (not recovery and int(fence["shell_revision"]) != int(evidence["shell_revision"]))
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
        binding_query = (
            "SELECT context_hash, case_id, source_id, source_revision, draft_revision, report_fingerprint, "
            "context_kind, active FROM archive_context_bindings WHERE attempt_id = ? "
            + ("AND active = 1" if not recovery else "")
        )
        binding = connection.execute(binding_query, (attempt_id,)).fetchall()
        allowed_lifecycles = {"archive_queued", "archiving"} if not recovery else {"archive_interrupted"}
        if (
            shell is None or source is None or draft is None or len(binding) != 1
            or int(shell["revision"]) != int(evidence["shell_revision"])
            or shell["source_id"] != evidence["source_id"]
            or shell["lifecycle"] not in allowed_lifecycles
            or source["case_id"] != evidence["case_id"]
            or int(source["revision"]) != int(evidence["source_revision"])
            or source["access_status"] != "available"
            or int(draft["revision"]) != int(evidence["draft_revision"])
            or draft["lifecycle"] not in allowed_lifecycles
            or report_fingerprint(json.loads(draft["report_json"])) != evidence["report_fingerprint"]
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
        cleanup = "succeeded" if row["staging_locator"] else "not_required"
        updated_attempt = connection.execute(
            "UPDATE archive_attempts SET status = 'succeeded', manifest_id = ?, "
            "manifest_source_key = ?, manifest_input_fingerprint = ?, manifest_archive_fingerprint = ?, "
            "cleanup_status = ?, error_code = NULL, finished_at = ?, revision = revision + 1 "
            "WHERE attempt_id = ?",
            (
                manifest_id, evidence["source_key"], evidence["input_fingerprint"],
                evidence["archive_fingerprint"], cleanup, now, attempt_id,
            ),
        )
        if updated_attempt.rowcount != 1:
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_STATE_INVALID")
        deactivate_bindings(connection, attempt_id)
        updated_shell = connection.execute(
            "UPDATE case_shells SET lifecycle = 'archive_verified', revision = revision + 1, "
            "updated_at = ? WHERE case_id = ? AND source_id = ? AND revision = ? "
            "AND lifecycle IN ('archive_queued', 'archiving', 'archive_interrupted')",
            (now, evidence["case_id"], evidence["source_id"], int(evidence["shell_revision"])),
        )
        if updated_shell.rowcount != 1:
            raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_CONFLICT")
        updated_draft = connection.execute(
            "UPDATE case_drafts SET lifecycle = 'archive_verified', updated_at = ? "
            "WHERE case_id = ? AND revision = ? AND lifecycle IN ('archive_queued', 'archiving', 'archive_interrupted')",
            (now, evidence["case_id"], int(evidence["draft_revision"])),
        )
        if updated_draft.rowcount != 1:
            raise WorkbenchPersistenceError("ARCHIVE_COMPLETION_EVIDENCE_CONFLICT")
        updated_fence = connection.execute(
            "UPDATE archive_publish_fences SET status = 'consumed', reason = 'ARCHIVE_COMPLETION_VERIFIED', updated_at = ? "
            "WHERE fence_id = ? AND status IN ('active', 'pending_verification')",
            (now, fence["fence_id"]),
        )
        if updated_fence.rowcount != 1:
            raise WorkbenchPersistenceError("ARCHIVE_PUBLISH_FENCE_STATE_INVALID")
    return _public(database, attempt_id)


def _public(database: WorkbenchDatabase, attempt_id: str) -> dict[str, Any]:
    return public_attempt(_row(database, attempt_id))


def _row(database: WorkbenchDatabase, attempt_id: str) -> Any:
    connection = database.connect()
    try:
        return connection.execute(
            "SELECT * FROM archive_attempts WHERE attempt_id = ?", (attempt_id,),
        ).fetchone()
    finally:
        connection.close()
