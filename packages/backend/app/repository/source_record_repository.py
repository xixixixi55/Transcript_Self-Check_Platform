"""SourceRecord persistence and restart-time source revalidation."""
from __future__ import annotations
import os
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from .workbench_constants import SOURCE_ACCESS_STATUSES, SOURCE_TYPES
from .workbench_database import WorkbenchDatabase, normalize_optional_utc, normalize_utc, utc_now
from .workbench_errors import RevisionConflictError, WorkbenchPersistenceError
from .workbench_repository_helpers import bool_int, json_text, public_source_record, row_json
from .workbench_serialization import validate_opaque_id
from .source_locator_repository import SourceLocatorRepository
from .archive_publish_fence_repository import invalidate_pending, reject_if_active
class SourceRecordRepository:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database
        self.locators = SourceLocatorRepository(database)
    def create(self, record: Mapping[str, Any]) -> dict[str, Any]:
        source_id = validate_opaque_id(record.get("source_id"))
        case_id = validate_opaque_id(record.get("case_id"))
        task_id = None if record.get("task_id") is None else validate_opaque_id(record.get("task_id"))
        allowed_root_id = validate_opaque_id(record.get("allowed_root_id"))
        status = str(record.get("access_status", "pending"))
        source_type = str(record.get("source_type", ""))
        if status not in SOURCE_ACCESS_STATUSES or source_type not in SOURCE_TYPES:
            raise WorkbenchPersistenceError("INVALID_SOURCE_STATUS")
        if status == "available":
            raise WorkbenchPersistenceError("SOURCE_REVALIDATION_REQUIRED")
        now = utc_now()
        fingerprint = record.get("fingerprint", "")
        if not isinstance(fingerprint, str) or not fingerprint:
            raise WorkbenchPersistenceError("INVALID_SOURCE_FINGERPRINT")
        fingerprint_json = {"value": fingerprint} if isinstance(fingerprint, str) else fingerprint
        metadata = _validate_metadata(record.get("metadata", {}))
        values = (
            source_id, 1, case_id, task_id, source_type,
            record["internal_path"], record["allowed_root"], allowed_root_id,
            json_text(metadata),
            json_text(fingerprint_json), status, bool_int(bool(record.get("requires_reselection", False))),
            normalize_optional_utc(record.get("last_verified_at")), 0, normalize_utc(record.get("created_at")), now,
            self.database.deployment_instance_id,
        )
        with self.database.transaction() as connection:
            try:
                connection.execute(
                    "INSERT INTO source_records(source_id, schema_version, case_id, task_id, source_type, internal_path, allowed_root, allowed_root_id, metadata_json, fingerprint_json, access_status, requires_reselection, last_verified_at, revision, created_at, updated_at, deployment_instance_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    values,
                )
            except Exception as error:
                raise WorkbenchPersistenceError("SOURCE_CREATE_FAILED") from error
        return self.get(source_id)
    def get(self, source_id: str) -> dict[str, Any]:
        source_id = validate_opaque_id(source_id)
        connection = self.database.connect()
        try:
            row = connection.execute("SELECT * FROM source_records WHERE source_id = ?", (source_id,)).fetchone()
        finally:
            connection.close()
        if row is None:
            raise WorkbenchPersistenceError("SOURCE_NOT_FOUND")
        return public_source_record(row)
    def get_internal_locator(self, source_id: str) -> dict[str, str]:
        """Internal repository use only; controllers must not expose this result."""
        source_id = validate_opaque_id(source_id)
        connection = self.database.connect()
        try:
            row = connection.execute(
                "SELECT internal_path, allowed_root FROM source_records WHERE source_id = ?", (source_id,)
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise WorkbenchPersistenceError("SOURCE_NOT_FOUND")
        raw_path = str(row[0])
        raw_root = str(row[1])
        if raw_path.startswith("locator://"):
            return self.locators.get(source_id)
        return {"internal_path": raw_path, "allowed_root": raw_root}
    def activate_pending(
        self, source_id: str, metadata: Mapping[str, Any], fingerprint: str,
    ) -> dict[str, Any]:
        """Commit the deferred source identity after the case shell exists."""
        source_id = validate_opaque_id(source_id)
        if not isinstance(fingerprint, str) or not fingerprint:
            raise WorkbenchPersistenceError("INVALID_SOURCE_FINGERPRINT")
        safe_metadata = _validate_metadata(metadata)
        now = utc_now()
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT case_id, access_status FROM source_records WHERE source_id = ?",
                (source_id,),
            ).fetchone()
            if row is None:
                raise WorkbenchPersistenceError("SOURCE_NOT_FOUND")
            reject_if_active(connection, case_id=row[0], source_id=source_id)
            invalidate_pending(connection, case_id=row[0], source_id=source_id)
            if row[1] != "pending":
                return self.get(source_id)
            updated = connection.execute(
                "UPDATE source_records SET metadata_json = ?, fingerprint_json = ?, access_status = 'available', requires_reselection = 0, revalidation_error_code = NULL, last_verified_at = ?, revision = revision + 1, updated_at = ? WHERE source_id = ? AND access_status = 'pending'",
                (json_text(safe_metadata), json_text({"value": fingerprint}), now, now, source_id),
            )
            if updated.rowcount != 1:
                raise WorkbenchPersistenceError("SOURCE_REVISION_CONFLICT")
        return self.get(source_id)
    def revalidate(self, source_id: str, *, current_fingerprint: str | None = None) -> dict[str, Any]:
        """Revalidate using a fingerprint freshly computed by the source adapter."""
        source_id = validate_opaque_id(source_id)
        if current_fingerprint is not None and not isinstance(current_fingerprint, str):
            raise WorkbenchPersistenceError("INVALID_SOURCE_FINGERPRINT")
        connection = self.database.connect()
        try:
            row = connection.execute("SELECT * FROM source_records WHERE source_id = ?", (source_id,)).fetchone()
        finally:
            connection.close()
        if row is None:
            raise WorkbenchPersistenceError("SOURCE_NOT_FOUND")
        valid = _source_is_current(row, current_fingerprint, self.get_internal_locator(source_id))
        status = "available" if valid else "requires_reselection"
        source_revision = int(row["revision"])
        with self.database.transaction() as transaction:
            reject_if_active(transaction, case_id=str(row["case_id"]), source_id=source_id)
            invalidate_pending(transaction, case_id=str(row["case_id"]), source_id=source_id)
            updated = transaction.execute(
                "UPDATE source_records SET access_status = ?, requires_reselection = ?, revalidation_error_code = NULL, last_verified_at = ?, revision = revision + 1, updated_at = ? WHERE source_id = ? AND revision = ?",
                (status, bool_int(not valid), utc_now(), utc_now(), source_id, source_revision),
            )
            if updated.rowcount != 1:
                raise WorkbenchPersistenceError("SOURCE_REVISION_CONFLICT")
        return self.get(source_id)
    def mark_pending_revalidation(self, source_id: str, error_code: str = "SOURCE_REVALIDATION_PENDING") -> dict[str, Any]:
        source_id = validate_opaque_id(source_id)
        now = utc_now()
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT case_id, revision FROM source_records WHERE source_id = ?", (source_id,),
            ).fetchone()
            if row is None:
                raise WorkbenchPersistenceError("SOURCE_NOT_FOUND")
            reject_if_active(connection, case_id=row[0], source_id=source_id)
            invalidate_pending(connection, case_id=row[0], source_id=source_id)
            connection.execute(
                "UPDATE source_records SET access_status = 'pending', requires_reselection = 0, revalidation_error_code = ?, updated_at = ?, revision = revision + 1 WHERE source_id = ?",
                (error_code, now, source_id),
            )
        return self.get(source_id)
    def pending_review_records(self) -> list[dict[str, int | str]]:
        connection = self.database.connect()
        try:
            rows = connection.execute(
                "SELECT source_records.source_id, source_records.revision FROM source_records JOIN case_shells ON case_shells.case_id = source_records.case_id WHERE source_records.access_status = 'pending' AND case_shells.report_available = 1",
            ).fetchall()
        finally:
            connection.close()
        return [{"source_id": str(row[0]), "revision": int(row[1])} for row in rows]
    def replace_for_case(self, case_id: str, record: Mapping[str, Any], expected_revision: int) -> dict[str, Any]:
        case_id = validate_opaque_id(case_id)
        source_id = validate_opaque_id(record.get("source_id"))
        task_id = validate_opaque_id(record.get("task_id"))
        allowed_root_id = validate_opaque_id(record.get("allowed_root_id"))
        source_type = str(record.get("source_type", ""))
        if source_type not in SOURCE_TYPES or not record.get("fingerprint"):
            raise WorkbenchPersistenceError("INVALID_SOURCE_RECORD")
        metadata = _validate_metadata(record.get("metadata", {}))
        now = utc_now()
        with self.database.transaction() as connection:
            case = connection.execute("SELECT source_id, parse_task_id, revision, lifecycle FROM case_shells WHERE case_id = ?", (case_id,)).fetchone()
            if case is None or case[1] != task_id:
                raise WorkbenchPersistenceError("CASE_NOT_FOUND")
            reject_if_active(connection, case_id=case_id, source_id=case[0])
            invalidate_pending(connection, case_id=case_id, source_id=case[0])
            if int(case[2]) != expected_revision:
                raise RevisionConflictError("case_shell", expected_revision, int(case[2]))
            if case[3] in {"archive_queued", "archiving"}:
                raise WorkbenchPersistenceError("SOURCE_REPLACEMENT_NOT_ALLOWED")
            task = connection.execute(
                "SELECT status, attempt FROM task_records WHERE task_id = ? AND case_id = ?",
                (task_id, case_id),
            ).fetchone()
            if task is None:
                raise WorkbenchPersistenceError("CASE_NOT_FOUND")
            if task[0] in {"queued", "running", "cancelling"}:
                raise WorkbenchPersistenceError("SOURCE_REPLACEMENT_NOT_ALLOWED")
            try:
                connection.execute(
                    "INSERT INTO source_records(source_id, schema_version, case_id, task_id, source_type, internal_path, allowed_root, allowed_root_id, metadata_json, fingerprint_json, access_status, requires_reselection, revalidation_error_code, last_verified_at, revision, created_at, updated_at, deployment_instance_id) VALUES (?, 1, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 0, NULL, NULL, 0, ?, ?, ?)",
                    (source_id, case_id, task_id, source_type, record["internal_path"], record["allowed_root"], allowed_root_id, json_text(metadata), json_text({"value": record["fingerprint"]}), now, now, self.database.deployment_instance_id),
                )
                connection.execute(
                    "UPDATE source_records SET access_status = 'requires_reselection', requires_reselection = 1, revalidation_error_code = NULL, revision = revision + 1, updated_at = ? WHERE source_id = ?",
                    (now, case[0]),
                )
                connection.execute("DELETE FROM case_drafts WHERE case_id = ?", (case_id,))
                connection.execute(
                    "UPDATE task_records SET status = 'queued', stage = 'parse', percent = NULL, counters_json = '{}', process_binding_json = NULL, error_code = NULL, error_summary = NULL, cancel_requested = 0, input_revision = input_revision + 1, attempt = ?, started_at = NULL, finished_at = NULL, revision = revision + 1 WHERE task_id = ? AND status NOT IN ('queued', 'running', 'cancelling')",
                    (int(task[1]) + 1, task_id),
                )
                updated = connection.execute(
                    "UPDATE case_shells SET source_id = ?, lifecycle = 'parse_queued', report_available = 0, revision = revision + 1, updated_at = ? WHERE case_id = ? AND revision = ?",
                    (source_id, now, case_id, expected_revision),
                )
                if updated.rowcount != 1:
                    raise RevisionConflictError("case_shell", expected_revision, expected_revision)
            except sqlite3.IntegrityError as error:
                raise WorkbenchPersistenceError("SOURCE_REPLACEMENT_FAILED") from error
        return self.get(source_id)
def _source_is_current(
    row: Mapping[str, Any], current_fingerprint: str | None, locator: Mapping[str, str],
) -> bool:
    try:
        candidate = Path(locator["internal_path"])
        root = Path(locator["allowed_root"])
        resolved_candidate = candidate.resolve(strict=True)
        resolved_root = root.resolve(strict=True)
        resolved_candidate.relative_to(resolved_root)
        source_type = str(row["source_type"])
        if source_type == "report_directory" and not resolved_candidate.is_dir():
            return False
        if source_type != "report_directory" and not resolved_candidate.is_file():
            return False
        if candidate.is_symlink() or not os.access(resolved_candidate, os.R_OK):
            return False
        metadata = row_json(row, "metadata_json")
        fingerprint = row_json(row, "fingerprint_json")
        if current_fingerprint is None or not isinstance(fingerprint, dict) or fingerprint.get("value") != current_fingerprint:
            return False
        stat = resolved_candidate.stat()
        if "size_bytes" in metadata and int(metadata["size_bytes"]) != int(stat.st_size):
            return False
        if "modified_time_ns" in metadata and int(metadata["modified_time_ns"]) != int(stat.st_mtime_ns):
            return False
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False
def _validate_metadata(value: Any) -> dict[str, str | int | float | bool]:
    if not isinstance(value, Mapping):
        raise WorkbenchPersistenceError("INVALID_SOURCE_METADATA")
    if any(
        not isinstance(key, str) or isinstance(item, (dict, list, tuple, bytes, bytearray))
        or not isinstance(item, (str, int, float, bool))
        for key, item in value.items()
    ):
        raise WorkbenchPersistenceError("INVALID_SOURCE_METADATA")
    return dict(value)
