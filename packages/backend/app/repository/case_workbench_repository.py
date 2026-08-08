"""CaseShell and CaseDraft repositories with optimistic revisions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .workbench_constants import CASE_LIFECYCLES, CASE_TRANSITIONS, REVIEWABLE_LIFECYCLES
from .workbench_database import WorkbenchDatabase, normalize_utc, utc_now
from .workbench_errors import RevisionConflictError, WorkbenchPersistenceError
from .workbench_legacy_report import validate_legacy_report
from .workbench_repository_helpers import bool_int, json_text, row_json
from .workbench_serialization import validate_field_states, validate_opaque_asset_refs, validate_opaque_id, validate_safe_string
from .archive_publish_fence_repository import invalidate_pending, reject_if_active
from .archive_context_binding_repository import (
    archive_stable_report_fingerprint,
    report_fingerprint,
)
from .case_tombstone_repository import shell_tombstone_projection


class CaseShellRepository:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database

    def create(self, shell: Mapping[str, Any]) -> dict[str, Any]:
        case_id = validate_opaque_id(shell.get("case_id"))
        source_id = validate_opaque_id(shell.get("source_id"))
        parse_task_id = validate_opaque_id(shell.get("parse_task_id"))
        now = utc_now()
        created_at = normalize_utc(shell.get("created_at"))
        case_number = None if shell.get("case_number") is None else validate_safe_string(shell["case_number"], "INVALID_CASE_SHELL")
        case_name = validate_safe_string(shell.get("case_name", ""), "INVALID_CASE_SHELL")
        case_summary = validate_safe_string(shell.get("case_summary", ""), "INVALID_CASE_SHELL")
        values = (
            case_id, 1, case_number, case_name, case_summary, source_id, parse_task_id,
            shell.get("lifecycle", "parse_queued"), 0, 0, created_at, now, self.database.deployment_instance_id,
        )
        if values[8] != 0 or values[6] is None or values[5] is None:
            raise WorkbenchPersistenceError("INVALID_CASE_SHELL")
        if values[7] not in {"case_created", "parse_queued", "parsing"}:
            raise WorkbenchPersistenceError("INVALID_CASE_SHELL")
        with self.database.transaction() as connection:
            try:
                connection.execute(
                    "INSERT INTO case_shells(case_id, schema_version, case_number, case_name, case_summary, source_id, parse_task_id, lifecycle, report_available, revision, created_at, updated_at, deployment_instance_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    values,
                )
            except Exception as error:
                raise WorkbenchPersistenceError("CASE_SHELL_CREATE_FAILED") from error
        return self.get(case_id)

    def get(self, case_id: str) -> dict[str, Any]:
        case_id = validate_opaque_id(case_id)
        connection = self.database.connect()
        try:
            row = connection.execute("SELECT * FROM case_shells WHERE case_id = ? AND deployment_instance_id = ?", (case_id, self.database.deployment_instance_id)).fetchone()
        finally:
            connection.close()
        if row is None:
            raise WorkbenchPersistenceError("CASE_NOT_FOUND")
        return _shell_dict(row)

    def list(self, offset: int, limit: int) -> list[dict[str, Any]]:
        if offset < 0 or limit < 1:
            raise WorkbenchPersistenceError("INVALID_PAGE")
        connection = self.database.connect()
        try:
            rows = connection.execute("SELECT * FROM case_shells WHERE deployment_instance_id = ? ORDER BY updated_at DESC, case_id DESC LIMIT ? OFFSET ?", (self.database.deployment_instance_id, limit, offset)).fetchall()
        finally:
            connection.close()
        return [_shell_dict(row) for row in rows]

    def update_lifecycle(self, case_id: str, lifecycle: str, expected_revision: int) -> dict[str, Any]:
        case_id = validate_opaque_id(case_id)
        if lifecycle not in CASE_LIFECYCLES:
            raise WorkbenchPersistenceError("INVALID_STATE_TRANSITION")
        if lifecycle == "archive_queued":
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_REQUIRED")
        with self.database.transaction() as connection:
            row = connection.execute("SELECT revision,record_cleaned FROM case_shells WHERE case_id = ? AND deployment_instance_id = ?", (case_id, self.database.deployment_instance_id)).fetchone()
            if row is None or bool(row["record_cleaned"]):
                raise WorkbenchPersistenceError("CASE_RECORD_CLEANED" if row is not None else "CASE_NOT_FOUND")
            reject_if_active(connection, case_id=case_id)
            invalidate_pending(connection, case_id=case_id)
            actual = int(row["revision"])
            if actual != expected_revision:
                raise RevisionConflictError("case_shell", expected_revision, actual)
            current_row = connection.execute("SELECT lifecycle, report_available FROM case_shells WHERE case_id = ? AND deployment_instance_id = ?", (case_id, self.database.deployment_instance_id)).fetchone()
            current = str(current_row[0])
            if lifecycle not in CASE_TRANSITIONS.get(str(current), set()):
                raise WorkbenchPersistenceError("INVALID_STATE_TRANSITION")
            if lifecycle in REVIEWABLE_LIFECYCLES:
                draft = connection.execute("SELECT 1 FROM case_drafts JOIN case_shells ON case_shells.case_id = case_drafts.case_id WHERE case_drafts.case_id = ? AND case_shells.deployment_instance_id = ?", (case_id, self.database.deployment_instance_id)).fetchone()
                if not bool(current_row[1]) or draft is None:
                    raise WorkbenchPersistenceError("DRAFT_NOT_REVIEWABLE")
            updated = connection.execute("UPDATE case_shells SET lifecycle = ?, revision = revision + 1, updated_at = ? WHERE case_id = ? AND deployment_instance_id = ? AND revision = ?", (lifecycle, utc_now(), case_id, self.database.deployment_instance_id, expected_revision))
            if updated.rowcount != 1:
                raise RevisionConflictError("case_shell", expected_revision, actual)
        return self.get(case_id)


class CaseDraftRepository:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database

    def save(self, draft: Mapping[str, Any], expected_revision: int | None = None) -> dict[str, Any]:
        lifecycle_was_submitted = "lifecycle" in draft
        lifecycle = str(draft.get("lifecycle", "review_ready"))
        if lifecycle_was_submitted and lifecycle == "archive_queued":
            raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_REQUIRED")
        if lifecycle not in REVIEWABLE_LIFECYCLES:
            raise WorkbenchPersistenceError("DRAFT_NOT_REVIEWABLE")
        report = validate_legacy_report(draft.get("report"))
        report_version = str(draft.get("report_version", "legacy-v1"))
        if not report_version.startswith("legacy-"):
            raise WorkbenchPersistenceError("INVALID_LEGACY_REPORT")
        validate_opaque_id(report_version)
        report_json = json_text(report)
        field_states_json = json_text(validate_field_states(draft.get("field_states", {})))
        asset_refs = validate_opaque_asset_refs(draft.get("asset_refs", []))
        asset_refs_json = json_text(asset_refs)
        template_ref = _validate_template_ref(draft.get("template_ref"))
        template_ref_json = None if template_ref is None else json_text(template_ref)
        archive_plan_id = None if draft.get("archive_plan_id") is None else validate_opaque_id(draft.get("archive_plan_id"))
        now = utc_now()
        case_id = validate_opaque_id(draft.get("case_id"))
        case_number = None if draft.get("case_number") is None else validate_safe_string(draft["case_number"], "INVALID_CASE_DRAFT")
        case_name = validate_safe_string(draft.get("case_name", ""), "INVALID_CASE_DRAFT")
        case_summary = validate_safe_string(draft.get("case_summary", ""), "INVALID_CASE_DRAFT")
        with self.database.transaction() as connection:
            shell = connection.execute("SELECT * FROM case_shells WHERE case_id = ? AND deployment_instance_id = ?", (case_id, self.database.deployment_instance_id)).fetchone()
            if shell is None or bool(shell["record_cleaned"]):
                raise WorkbenchPersistenceError("CASE_RECORD_CLEANED" if shell is not None else "CASE_NOT_FOUND")
            reject_if_active(connection, case_id=case_id)
            invalidate_pending(connection, case_id=case_id)
            asset_ids = [str(item["asset_id"]) for item in asset_refs]
            if asset_ids:
                placeholders = ", ".join("?" for _ in asset_ids)
                rows = connection.execute(
                    f"SELECT asset_references.asset_id, asset_references.asset_kind, asset_references.fingerprint, asset_references.metadata_json FROM asset_references JOIN case_shells ON case_shells.case_id = asset_references.case_id WHERE asset_references.case_id = ? AND case_shells.deployment_instance_id = ? AND asset_references.asset_id IN ({placeholders})",
                    (case_id, self.database.deployment_instance_id, *asset_ids),
                ).fetchall()
                registered = {str(row["asset_id"]): row for row in rows}
                if set(registered) != set(asset_ids):
                    raise WorkbenchPersistenceError("ASSET_REFERENCE_NOT_FOUND")
                for reference in asset_refs:
                    stored = registered[reference["asset_id"]]
                    if reference["asset_kind"] != stored["asset_kind"]:
                        raise WorkbenchPersistenceError("ASSET_REFERENCE_MISMATCH")
                    if "fingerprint" in reference and reference["fingerprint"] != stored["fingerprint"]:
                        raise WorkbenchPersistenceError("ASSET_REFERENCE_MISMATCH")
                    if "metadata" in reference and reference["metadata"] != row_json(stored, "metadata_json"):
                        raise WorkbenchPersistenceError("ASSET_REFERENCE_MISMATCH")
            existing = connection.execute("SELECT case_drafts.revision, case_drafts.created_at, case_drafts.report_json FROM case_drafts JOIN case_shells ON case_shells.case_id = case_drafts.case_id WHERE case_drafts.case_id = ? AND case_shells.deployment_instance_id = ?", (case_id, self.database.deployment_instance_id)).fetchone()
            current_lifecycle = str(shell["lifecycle"])
            if existing and current_lifecycle in {"archive_queued", "archiving"}:
                previous_report = row_json(existing, "report_json")
                metadata_changed = any(
                    key in draft and draft.get(key) != shell[key]
                    for key in ("case_number", "case_name", "case_summary")
                )
                if (
                    metadata_changed
                    or archive_stable_report_fingerprint(previous_report)
                    != archive_stable_report_fingerprint(report)
                ):
                    raise WorkbenchPersistenceError("ARCHIVE_DRAFT_EDIT_NOT_ALLOWED")
            if existing and not lifecycle_was_submitted:
                lifecycle = current_lifecycle
            if not existing and lifecycle not in CASE_TRANSITIONS.get(current_lifecycle, set()):
                raise WorkbenchPersistenceError("DRAFT_NOT_REVIEWABLE")
            if existing and lifecycle != current_lifecycle and lifecycle not in CASE_TRANSITIONS.get(current_lifecycle, set()):
                raise WorkbenchPersistenceError("INVALID_STATE_TRANSITION")
            actual = int(existing[0]) if existing else 0
            if expected_revision is not None and actual != expected_revision:
                raise RevisionConflictError("case_draft", expected_revision, actual)
            revision = actual + 1
            values = (
                case_id, 1, report_json, report_version,
                field_states_json, asset_refs_json, template_ref_json, archive_plan_id,
                lifecycle, revision, existing[1] if existing else now, now,
            )
            if existing:
                updated = connection.execute("UPDATE case_drafts SET schema_version = ?, report_json = ?, report_version = ?, field_states_json = ?, asset_refs_json = ?, template_ref_json = ?, archive_plan_id = ?, lifecycle = ?, revision = ?, updated_at = ? WHERE case_id = ? AND revision = ? AND EXISTS (SELECT 1 FROM case_shells WHERE case_id = case_drafts.case_id AND deployment_instance_id = ?)", (values[1], values[2], values[3], values[4], values[5], values[6], values[7], values[8], values[9], values[11], case_id, actual, self.database.deployment_instance_id))
                if updated.rowcount != 1:
                    raise RevisionConflictError("case_draft", actual, actual)
            else:
                connection.execute(
                    "INSERT INTO case_drafts(case_id, schema_version, report_json, report_version, field_states_json, asset_refs_json, template_ref_json, archive_plan_id, lifecycle, revision, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    values,
                )
            shell_revision = int(shell["revision"])
            updated_shell = connection.execute("UPDATE case_shells SET case_number = ?, case_name = ?, case_summary = ?, report_available = 1, lifecycle = ?, revision = revision + 1, updated_at = ? WHERE case_id = ? AND deployment_instance_id = ? AND revision = ?", (case_number if "case_number" in draft else shell["case_number"], case_name if "case_name" in draft else shell["case_name"], case_summary if "case_summary" in draft else shell["case_summary"], lifecycle, now, case_id, self.database.deployment_instance_id, shell_revision))
            if updated_shell.rowcount != 1:
                raise RevisionConflictError("case_shell", shell_revision, shell_revision)
            if existing and current_lifecycle in {"archive_queued", "archiving"}:
                _sync_active_archive_draft(
                    connection, case_id, actual, revision,
                    report_fingerprint(row_json(existing, "report_json")),
                    report_fingerprint(report),
                    self.database.deployment_instance_id,
                )
        return self.get(case_id)

    def get(self, case_id: str) -> dict[str, Any]:
        case_id = validate_opaque_id(case_id)
        connection = self.database.connect()
        try:
            row = connection.execute(
                "SELECT case_drafts.*, case_shells.case_number, case_shells.case_name, case_shells.case_summary, case_shells.report_available, case_shells.record_cleaned FROM case_drafts JOIN case_shells ON case_shells.case_id = case_drafts.case_id WHERE case_drafts.case_id = ? AND case_shells.deployment_instance_id = ?",
                (case_id, self.database.deployment_instance_id),
            ).fetchone()
        finally:
            connection.close()
        if row is None or bool(row["record_cleaned"]):
            raise WorkbenchPersistenceError("CASE_RECORD_CLEANED" if row is not None else "DRAFT_NOT_FOUND")
        if not bool(row["report_available"]) or row["lifecycle"] not in REVIEWABLE_LIFECYCLES:
            raise WorkbenchPersistenceError("DRAFT_NOT_REVIEWABLE")
        validate_legacy_report(row_json(row, "report_json"))
        validate_field_states(row_json(row, "field_states_json"))
        validate_opaque_asset_refs(row_json(row, "asset_refs_json"))
        return _draft_dict(row)


def _shell_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": int(row["schema_version"]), "case_id": row["case_id"],
        "case_number": row["case_number"], "case_name": row["case_name"], "case_summary": row["case_summary"],
        "source_id": row["source_id"],
        "parse_task_id": row["parse_task_id"], "lifecycle": row["lifecycle"],
        "report_available": bool(row["report_available"]), "revision": int(row["revision"]),
        "created_at": row["created_at"], "updated_at": row["updated_at"],
        **shell_tombstone_projection(row),
    }


def _validate_template_ref(value: Any) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) != {"template_id", "version"}:
        raise WorkbenchPersistenceError("INVALID_TEMPLATE_REFERENCE")
    return {
        "template_id": validate_opaque_id(value["template_id"]),
        "version": validate_opaque_id(value["version"]),
    }


def _sync_active_archive_draft(
    connection: Any, case_id: str, old_revision: int, new_revision: int,
    old_fingerprint: str, new_fingerprint: str, deployment_id: str,
) -> None:
    attempts = connection.execute(
        "SELECT attempt_id FROM archive_attempts WHERE case_id=? AND deployment_instance_id=? "
        "AND status IN ('accepted','running') ORDER BY created_at DESC",
        (case_id, deployment_id),
    ).fetchall()
    if len(attempts) != 1:
        raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_BINDING_STALE")
    attempt_id = str(attempts[0]["attempt_id"])
    updated_attempt = connection.execute(
        "UPDATE archive_attempts SET draft_revision=?, report_fingerprint=?, revision=revision+1 "
        "WHERE attempt_id=? AND deployment_instance_id=? AND draft_revision=? "
        "AND report_fingerprint=? AND status IN ('accepted','running')",
        (new_revision, new_fingerprint, attempt_id, deployment_id, old_revision, old_fingerprint),
    )
    updated_binding = connection.execute(
        "UPDATE archive_context_bindings SET draft_revision=?, report_fingerprint=? "
        "WHERE attempt_id=? AND active=1 AND draft_revision=? AND report_fingerprint=?",
        (new_revision, new_fingerprint, attempt_id, old_revision, old_fingerprint),
    )
    if updated_attempt.rowcount != 1 or updated_binding.rowcount != 1:
        raise WorkbenchPersistenceError("ARCHIVE_ATTEMPT_BINDING_STALE")


def _draft_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": int(row["schema_version"]), "case_id": row["case_id"],
        "case_number": row["case_number"], "case_name": row["case_name"], "case_summary": row["case_summary"],
        "report": row_json(row, "report_json"), "report_version": row["report_version"],
        "field_states": row_json(row, "field_states_json"), "asset_refs": row_json(row, "asset_refs_json"),
        "template_ref": None if row["template_ref_json"] is None else row_json(row, "template_ref_json"),
        "archive_plan_id": row["archive_plan_id"], "lifecycle": row["lifecycle"],
        "revision": int(row["revision"]), "created_at": row["created_at"], "updated_at": row["updated_at"],
    }
