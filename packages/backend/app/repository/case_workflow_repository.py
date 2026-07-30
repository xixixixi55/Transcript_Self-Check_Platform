"""Atomic persistence operations used by the Phase 1B workbench services."""
from __future__ import annotations
import sqlite3
import secrets
from collections.abc import Mapping
from typing import Any
from .workbench_constants import CASE_TRANSITIONS, TASK_TRANSITIONS
from .workbench_database import WorkbenchDatabase, utc_now
from .workbench_errors import WorkbenchPersistenceError
from .workbench_legacy_report import validate_legacy_report
from .workbench_repository_helpers import bool_int, json_text
from .workbench_serialization import (
    validate_field_states,
    validate_opaque_asset_refs,
    validate_opaque_id,
    validate_safe_string,
)
from .case_archive_decision_repository import CaseArchiveDecisionRepository
from .archive_publish_fence_repository import reject_if_active
class CaseWorkflowRepository:
    """Keep cross-record case/task/source changes in one SQLite transaction."""
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database
        self.archive_decisions = CaseArchiveDecisionRepository(database)
    def create_submission(
        self, shell: Mapping[str, Any], task: Mapping[str, Any], source: Mapping[str, Any],
        identity: Mapping[str, Any] | None = None,
    ) -> None:
        case_id = validate_opaque_id(shell.get("case_id"))
        task_id = validate_opaque_id(task.get("task_id"))
        source_id = validate_opaque_id(source.get("source_id"))
        if task.get("case_id") != case_id or source.get("case_id") != case_id:
            raise WorkbenchPersistenceError("INVALID_CASE_SUBMISSION")
        if task.get("task_id") != source.get("task_id"):
            raise WorkbenchPersistenceError("INVALID_CASE_SUBMISSION")
        case_number = _optional_safe(shell.get("case_number"), "INVALID_CASE_SHELL")
        case_name = validate_safe_string(shell.get("case_name", ""), "INVALID_CASE_SHELL")
        case_summary = validate_safe_string(shell.get("case_summary", ""), "INVALID_CASE_SHELL")
        source_type = str(source.get("source_type", ""))
        if source_type not in {"report_directory", "report_archive", "uploaded_file", "other"}:
            raise WorkbenchPersistenceError("INVALID_SOURCE_STATUS")
        if source.get("access_status", "pending") != "pending":
            raise WorkbenchPersistenceError("SOURCE_REVALIDATION_REQUIRED")
        metadata = _metadata(source.get("metadata", {}))
        fingerprint = source.get("fingerprint")
        if not isinstance(fingerprint, str) or not fingerprint:
            raise WorkbenchPersistenceError("INVALID_SOURCE_FINGERPRINT")
        now = utc_now()
        try:
            with self.database.transaction() as connection:
                connection.execute(
                    "INSERT INTO case_shells VALUES (?, 1, ?, ?, ?, ?, ?, 'parse_queued', 0, 0, ?, ?)",
                    (case_id, case_number, case_name, case_summary, source_id, task_id, now, now),
                )
                connection.execute(
                    "INSERT INTO task_records(task_id, schema_version, case_id, kind, status, stage, percent, counters_json, input_revision, attempt, process_binding_json, error_code, error_summary, cancel_requested, created_at, started_at, updated_at, finished_at, allowed_actions_json, revision) VALUES (?, 1, ?, 'parse', 'queued', 'parse', NULL, ?, 0, 0, NULL, NULL, NULL, 0, ?, NULL, ?, NULL, '[]', 0)",
                    (task_id, case_id, json_text({}), now, now),
                )
                connection.execute(
                    "INSERT INTO source_records(source_id, schema_version, case_id, task_id, source_type, internal_path, allowed_root, allowed_root_id, metadata_json, fingerprint_json, access_status, requires_reselection, revalidation_error_code, last_verified_at, revision, created_at, updated_at) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 0, NULL, NULL, 0, ?, ?)",
                    (
                        source_id, case_id, task_id, source_type, source["internal_path"],
                        source["allowed_root"], validate_opaque_id(source["allowed_root_id"]),
                        json_text(metadata), json_text({"value": fingerprint}), now, now,
                    ),
                )
                if identity is not None:
                    _insert_audit(connection, identity, case_id, task_id, now)
        except sqlite3.IntegrityError as error:
            raise WorkbenchPersistenceError("CASE_SUBMISSION_CREATE_FAILED") from error
    def start_parse(self, case_id: str, task_id: str) -> None:
        self._transition_parse(case_id, task_id, "parsing", "running")
    def complete_parse(
        self,
        case_id: str,
        task_id: str,
        report: Mapping[str, Any],
        field_states: Mapping[str, Any],
        *,
        report_version: str = "legacy-v1",
        asset_refs: list[Mapping[str, Any]] | None = None,
    ) -> None:
        validate_legacy_report(report)
        validate_field_states(field_states)
        refs = validate_opaque_asset_refs(asset_refs or [])
        validate_opaque_id(report_version)
        now = utc_now()
        with self.database.transaction() as connection:
            reject_if_active(connection, case_id=case_id)
            shell = connection.execute("SELECT * FROM case_shells WHERE case_id = ?", (case_id,)).fetchone()
            task = connection.execute("SELECT * FROM task_records WHERE task_id = ?", (task_id,)).fetchone()
            source = connection.execute("SELECT access_status FROM source_records WHERE source_id = ?", (shell["source_id"],)).fetchone() if shell else None
            if shell is None or task is None:
                raise WorkbenchPersistenceError("CASE_NOT_FOUND")
            if task["case_id"] != case_id or task["status"] != "running":
                raise WorkbenchPersistenceError("INVALID_TASK_TRANSITION")
            if shell["lifecycle"] != "parsing":
                raise WorkbenchPersistenceError("INVALID_STATE_TRANSITION")
            if source is None or source[0] not in {"pending", "available"}:
                raise WorkbenchPersistenceError("SOURCE_RESELECTION_REQUIRED")
            _ensure_assets(connection, case_id, refs)
            connection.execute(
                "INSERT INTO case_drafts VALUES (?, 1, ?, ?, ?, ?, NULL, NULL, 'review_ready', 1, ?, ?)",
                (case_id, json_text(report), report_version, json_text(field_states), json_text(refs), now, now),
            )
            shell_updated = connection.execute(
                "UPDATE case_shells SET report_available = 1, lifecycle = 'review_ready', revision = revision + 1, updated_at = ? WHERE case_id = ? AND lifecycle = 'parsing'",
                (now, case_id),
            )
            if shell_updated.rowcount != 1:
                raise WorkbenchPersistenceError("INVALID_STATE_TRANSITION")
            updated = connection.execute(
                "UPDATE task_records SET status = 'succeeded', percent = 100, finished_at = ?, revision = revision + 1 WHERE task_id = ? AND status = 'running'",
                (now, task_id),
            )
            if updated.rowcount != 1:
                raise WorkbenchPersistenceError("INVALID_TASK_TRANSITION")
    def fail_parse(self, case_id: str, task_id: str, error_code: str) -> None:
        safe_code = validate_safe_string(error_code, "INVALID_TASK_RECORD")
        now = utc_now()
        with self.database.transaction() as connection:
            reject_if_active(connection, case_id=case_id)
            shell = connection.execute("SELECT lifecycle FROM case_shells WHERE case_id = ?", (case_id,)).fetchone()
            task = connection.execute("SELECT status FROM task_records WHERE task_id = ? AND case_id = ?", (task_id, case_id)).fetchone()
            if shell is None or task is None:
                raise WorkbenchPersistenceError("CASE_NOT_FOUND")
            if task[0] not in {"queued", "running", "interrupted"}:
                raise WorkbenchPersistenceError("INVALID_TASK_TRANSITION")
            if shell[0] != "parse_failed_retryable":
                shell_updated = connection.execute(
                    "UPDATE case_shells SET lifecycle = 'parse_failed_retryable', report_available = 0, revision = revision + 1, updated_at = ? WHERE case_id = ? AND lifecycle IN ('case_created', 'parse_queued', 'parsing')",
                    (now, case_id),
                )
                if shell_updated.rowcount != 1:
                    raise WorkbenchPersistenceError("INVALID_STATE_TRANSITION")
            updated = connection.execute(
                "UPDATE task_records SET status = 'failed_retryable', error_code = ?, error_summary = ?, finished_at = ?, revision = revision + 1 WHERE task_id = ? AND status IN ('queued', 'running', 'interrupted')",
                (safe_code, safe_code, now, task_id),
            )
            if updated.rowcount != 1:
                raise WorkbenchPersistenceError("INVALID_TASK_TRANSITION")
    def decide_archive(self, case_id: str, decision: str, expected_revision: int) -> None:
        self.archive_decisions.decide(case_id, decision, expected_revision)
    def retry_parse(self, case_id: str, task_id: str) -> None:
        now = utc_now()
        with self.database.transaction() as connection:
            reject_if_active(connection, case_id=case_id)
            shell = connection.execute("SELECT lifecycle FROM case_shells WHERE case_id = ?", (case_id,)).fetchone()
            task = connection.execute("SELECT status, attempt FROM task_records WHERE task_id = ? AND case_id = ?", (task_id, case_id)).fetchone()
            if shell is None or task is None:
                raise WorkbenchPersistenceError("CASE_NOT_FOUND")
            if shell[0] != "parse_failed_retryable" or task[0] not in {"failed_retryable", "interrupted"}:
                raise WorkbenchPersistenceError("PARSE_RETRY_NOT_ALLOWED")
            connection.execute(
                "UPDATE case_shells SET lifecycle = 'parse_queued', revision = revision + 1, updated_at = ? WHERE case_id = ?",
                (now, case_id),
            )
            connection.execute(
                "UPDATE task_records SET status = 'queued', percent = NULL, error_code = NULL, error_summary = NULL, cancel_requested = 0, attempt = ?, started_at = NULL, finished_at = NULL, revision = revision + 1 WHERE task_id = ?",
                (int(task[1]) + 1, task_id),
            )
    def cancel_parse(self, case_id: str, task_id: str, expected_revision: int) -> None:
        now = utc_now()
        with self.database.transaction() as connection:
            reject_if_active(connection, case_id=case_id)
            shell = connection.execute("SELECT lifecycle FROM case_shells WHERE case_id = ?", (case_id,)).fetchone()
            task = connection.execute("SELECT status, revision FROM task_records WHERE task_id = ? AND case_id = ?", (task_id, case_id)).fetchone()
            if shell is None or task is None:
                raise WorkbenchPersistenceError("CASE_NOT_FOUND")
            if int(task[1]) != expected_revision:
                raise WorkbenchPersistenceError("REVISION_CONFLICT")
            if task[0] == "queued" and shell[0] == "parse_queued":
                next_status, next_lifecycle = "cancelled", "cancelled"
            elif task[0] == "running" and shell[0] == "parsing":
                next_status, next_lifecycle = "cancelling", "cancelling"
            else:
                raise WorkbenchPersistenceError("TASK_NOT_CANCELLABLE")
            connection.execute("UPDATE case_shells SET lifecycle = ?, revision = revision + 1, updated_at = ? WHERE case_id = ?", (next_lifecycle, now, case_id))
            updated = connection.execute("UPDATE task_records SET status = ?, cancel_requested = 1, revision = revision + 1, finished_at = ? WHERE task_id = ? AND revision = ?", (next_status, now if next_status == "cancelled" else None, task_id, expected_revision))
            if updated.rowcount != 1:
                raise WorkbenchPersistenceError("REVISION_CONFLICT")
    def recover_after_restart(self) -> list[str]:
        interrupted: list[str] = []
        now = utc_now()
        with self.database.transaction() as connection:
            rows = connection.execute("SELECT task_id, case_id, kind, status FROM task_records WHERE (kind = 'parse' AND status IN ('queued','running','cancelling')) OR (kind = 'archive' AND status IN ('running','cancelling'))").fetchall()
            for row in rows:
                next_status = "failed_retryable" if row[3] == "queued" else "interrupted"
                worker_state = "waiting_reclaim" if row[2] == "archive" else None
                actions = '["view_details","retry"]' if row[2] == "archive" else "[]"
                updated = connection.execute("UPDATE task_records SET status = ?, error_code = 'TASK_RESTART_INTERRUPTED', error_summary = 'TASK_RESTART_INTERRUPTED', worker_state = ?, allowed_actions_json = ?, updated_at = ?, revision = revision + 1 WHERE task_id = ? AND status IN ('queued','running','cancelling')", (next_status, worker_state, actions, now, row[0]))
                if updated.rowcount != 1: raise WorkbenchPersistenceError("INVALID_TASK_TRANSITION")
                if row[2] == "parse":
                    shell_updated = connection.execute("UPDATE case_shells SET lifecycle = 'parse_failed_retryable', report_available = 0, revision = revision + 1, updated_at = ? WHERE case_id = ? AND lifecycle IN ('parse_queued', 'parsing', 'cancelling')", (now, row[1]))
                    if shell_updated.rowcount != 1: raise WorkbenchPersistenceError("INVALID_STATE_TRANSITION")
                interrupted.append(str(row[0]))
        return interrupted
    def delete_preflight(self, case_id: str) -> dict[str, Any]:
        with self.database.connect() as connection:
            case = connection.execute("SELECT lifecycle FROM case_shells WHERE case_id = ?", (case_id,)).fetchone()
            if case is None:
                raise WorkbenchPersistenceError("CASE_NOT_FOUND")
            blockers: list[str] = []
            if connection.execute("SELECT 1 FROM task_records WHERE case_id = ? AND status IN ('queued', 'running', 'cancelling', 'interrupted', 'failed_retryable')", (case_id,)).fetchone():
                blockers.append("ACTIVE_OR_RETRYABLE_TASK")
            if connection.execute("SELECT 1 FROM edit_leases WHERE case_id = ? AND status = 'active'", (case_id,)).fetchone():
                blockers.append("ACTIVE_EDIT_LEASE")
            if case[0] in {"parsing", "archiving", "exporting_word"}:
                blockers.append("CASE_BUSY")
            return {"allowed": not blockers, "blockers": blockers}
    def _transition_parse(self, case_id: str, task_id: str, lifecycle: str, status: str) -> None:
        with self.database.transaction() as connection:
            reject_if_active(connection, case_id=case_id)
            shell = connection.execute("SELECT lifecycle FROM case_shells WHERE case_id = ?", (case_id,)).fetchone()
            task = connection.execute("SELECT status FROM task_records WHERE task_id = ? AND case_id = ?", (task_id, case_id)).fetchone()
            if shell is None or task is None:
                raise WorkbenchPersistenceError("CASE_NOT_FOUND")
            if lifecycle not in CASE_TRANSITIONS.get(str(shell[0]), set()) or status not in TASK_TRANSITIONS.get(str(task[0]), set()):
                raise WorkbenchPersistenceError("INVALID_STATE_TRANSITION")
            now = utc_now()
            connection.execute("UPDATE case_shells SET lifecycle = ?, revision = revision + 1, updated_at = ? WHERE case_id = ?", (lifecycle, now, case_id))
            connection.execute("UPDATE task_records SET status = ?, started_at = ?, revision = revision + 1 WHERE task_id = ?", (status, now, task_id))
def _optional_safe(value: Any, code: str) -> str | None:
    return None if value is None else validate_safe_string(value, code)
def _metadata(value: Any) -> dict[str, str | int | float | bool]:
    if not isinstance(value, Mapping) or any(not isinstance(k, str) or isinstance(v, (dict, list, tuple, bytes, bytearray)) or not isinstance(v, (str, int, float, bool)) for k, v in value.items()):
        raise WorkbenchPersistenceError("INVALID_SOURCE_METADATA")
    return dict(value)
def _ensure_assets(connection: Any, case_id: str, refs: list[Mapping[str, Any]]) -> None:
    if not refs:
        return
    ids = [str(item["asset_id"]) for item in refs]
    placeholders = ",".join("?" for _ in ids)
    rows = connection.execute(f"SELECT asset_id FROM asset_references WHERE case_id = ? AND asset_id IN ({placeholders})", (case_id, *ids)).fetchall()
    if len(rows) != len(ids):
        raise WorkbenchPersistenceError("ASSET_REFERENCE_NOT_FOUND")
def _insert_audit(connection: Any, identity: Mapping[str, Any], case_id: str, task_id: str, now: str) -> None:
    if identity.get("identity_kind") != "local_session" or identity.get("deployment_instance_id") is None:
        raise WorkbenchPersistenceError("UNAUTHENTICATED_IDENTITY_REQUIRED")
    client_id = validate_opaque_id(identity.get("client_instance_id"))
    session_id = validate_opaque_id(identity.get("session_id"))
    deployment_id = validate_opaque_id(identity.get("deployment_instance_id"))
    display_name = identity.get("local_display_name")
    if display_name is not None:
        display_name = validate_safe_string(display_name, "INVALID_CLIENT_IDENTITY")
    connection.execute(
        "INSERT INTO audit_events VALUES (?, 'case_submitted', ?, ?, ?, ?, 'local_session', ?, ?, '{}', ?)",
        (f"audit-{secrets.token_hex(16)}", deployment_id, client_id, session_id, display_name, case_id, task_id, now),
    )
