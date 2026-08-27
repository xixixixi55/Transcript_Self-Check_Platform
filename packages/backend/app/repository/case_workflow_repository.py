"""Atomic persistence operations used by the Phase 1B workbench services."""
from __future__ import annotations
import secrets
import sqlite3
from collections.abc import Mapping
from typing import Any
from .workbench_constants import CASE_TRANSITIONS, TASK_TRANSITIONS
from .workbench_database import WorkbenchDatabase, utc_now
from .workbench_errors import WorkbenchPersistenceError
from .task_recovery_repository import recover_tasks_after_restart
from .workbench_legacy_report import validate_legacy_report
from .workbench_repository_helpers import bool_int, case_shell_values, json_text, optional_safe
from .workbench_serialization import (
    validate_field_states,
    validate_opaque_asset_refs,
    validate_opaque_id,
    validate_safe_string,
)
from .case_archive_decision_repository import CaseArchiveDecisionRepository
from .case_deletion_repository import CaseDeletionRepository
from .case_workbench_repository import _validate_template_ref
from .archive_publish_fence_repository import reject_if_active


def normalize_source_metadata(value: Any) -> dict[str, str | int | float | bool]:
    if not isinstance(value, Mapping) or any(
        not isinstance(key, str)
        or isinstance(item, (dict, list, tuple, bytes, bytearray))
        or not isinstance(item, (str, int, float, bool))
        for key, item in value.items()
    ):
        raise WorkbenchPersistenceError("INVALID_SOURCE_METADATA")
    return dict(value)


def ensure_asset_refs(connection: Any, case_id: str, refs: list[Mapping[str, Any]]) -> None:
    if not refs:
        return
    ids = [str(item["asset_id"]) for item in refs]
    placeholders = ",".join("?" for _ in ids)
    rows = connection.execute(
        f"SELECT asset_id FROM asset_references WHERE case_id = ? AND asset_id IN ({placeholders})",
        (case_id, *ids),
    ).fetchall()
    if len(rows) != len(ids):
        raise WorkbenchPersistenceError("ASSET_REFERENCE_NOT_FOUND")


def insert_audit_event(
    connection: Any, identity: Mapping[str, Any], case_id: str, task_id: str, now: str,
) -> None:
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


class CaseWorkflowRepository:
    """Keep cross-record case/task/source changes in one SQLite transaction."""
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database
        self.archive_decisions = CaseArchiveDecisionRepository(database)
        self.deletion = CaseDeletionRepository(database)
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
        case_number = optional_safe(shell.get("case_number"), "INVALID_CASE_SHELL")
        case_name = validate_safe_string(shell.get("case_name", ""), "INVALID_CASE_SHELL")
        case_summary = validate_safe_string(shell.get("case_summary", ""), "INVALID_CASE_SHELL")
        source_type = str(source.get("source_type", ""))
        if source_type not in {"report_directory", "report_archive", "uploaded_file", "other"}:
            raise WorkbenchPersistenceError("INVALID_SOURCE_STATUS")
        if source.get("access_status", "pending") != "pending":
            raise WorkbenchPersistenceError("SOURCE_REVALIDATION_REQUIRED")
        metadata = normalize_source_metadata(source.get("metadata", {}))
        fingerprint = source.get("fingerprint")
        if not isinstance(fingerprint, str) or not fingerprint:
            raise WorkbenchPersistenceError("INVALID_SOURCE_FINGERPRINT")
        now = utc_now()
        try:
            with self.database.transaction() as connection:
                connection.execute(
                    "INSERT INTO case_shells(case_id,schema_version,case_number,case_name,case_summary,"
                    "source_id,parse_task_id,lifecycle,report_available,revision,created_at,updated_at,"
                    "deployment_instance_id) VALUES (?,1,?,?,?,?,?,'parse_queued',0,0,?,?,?)",
                    (case_id, case_number, case_name, case_summary, source_id, task_id, now, now,
                     self.database.deployment_instance_id),
                )
                connection.execute(
                    "INSERT INTO task_records(task_id,schema_version,case_id,kind,status,stage,percent,"
                    "counters_json,input_revision,attempt,process_binding_json,error_code,error_summary,"
                    "cancel_requested,created_at,started_at,updated_at,finished_at,allowed_actions_json,"
                    "revision,deployment_instance_id) VALUES (?,1,?,'parse','queued','parse',NULL,?,0,0,"
                    "NULL,NULL,NULL,0,?,NULL,?,NULL,'[]',0,?)",
                    (task_id, case_id, json_text({}), now, now, self.database.deployment_instance_id),
                )
                connection.execute(
                    "INSERT INTO source_records(source_id,schema_version,case_id,task_id,source_type,"
                    "internal_path,allowed_root,allowed_root_id,metadata_json,fingerprint_json,access_status,"
                    "requires_reselection,revalidation_error_code,last_verified_at,revision,created_at,"
                    "updated_at,deployment_instance_id) VALUES (?,1,?,?,?,?,?,?,?,?, 'pending',0,NULL,NULL,0,?,?,?)",
                    (
                        source_id, case_id, task_id, source_type, source["internal_path"],
                        source["allowed_root"], validate_opaque_id(source["allowed_root_id"]),
                        json_text(metadata), json_text({"value": fingerprint}), now, now,
                        self.database.deployment_instance_id,
                    ),
                )
                if identity is not None:
                    insert_audit_event(connection, identity, case_id, task_id, now)
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
        template_ref: Mapping[str, Any] | None = None,
        case_metadata: Mapping[str, Any] | None = None,
    ) -> None:
        validate_legacy_report(report)
        validate_field_states(field_states)
        refs = validate_opaque_asset_refs(asset_refs or [])
        normalized_template_ref = _validate_template_ref(template_ref)
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
            ensure_asset_refs(connection, case_id, refs)
            case_number, case_name, case_summary = case_shell_values(shell, case_metadata)
            connection.execute(
                "INSERT INTO case_drafts VALUES (?, 1, ?, ?, ?, ?, ?, NULL, 'review_ready', 1, ?, ?)",
                (
                    case_id, json_text(report), report_version, json_text(field_states),
                    json_text(refs),
                    None if normalized_template_ref is None else json_text(normalized_template_ref),
                    now, now,
                ),
            )
            shell_updated = connection.execute(
                "UPDATE case_shells SET case_number = ?, case_name = ?, case_summary = ?, report_available = 1, lifecycle = 'review_ready', revision = revision + 1, updated_at = ? WHERE case_id = ? AND lifecycle = 'parsing'",
                (case_number, case_name, case_summary, now, case_id),
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
    def recover_after_restart(self, *, include_archive: bool = True) -> list[str]:
        return recover_tasks_after_restart(
            self.database, include_archive=include_archive,
        )
    def delete_preflight(self, case_id: str) -> dict[str, Any]:
        return self.deletion.preflight(case_id)

    def delete_case(self, case_id: str) -> dict[str, Any]:
        return self.deletion.delete_case(case_id)
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
