"""SourceRecord persistence and restart-time source revalidation."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .workbench_constants import SOURCE_ACCESS_STATUSES, SOURCE_TYPES
from .workbench_database import WorkbenchDatabase, normalize_optional_utc, normalize_utc, utc_now
from .workbench_errors import WorkbenchPersistenceError
from .workbench_repository_helpers import bool_int, json_text, public_source_record, row_json
from .workbench_serialization import validate_opaque_id


class SourceRecordRepository:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database

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
        )
        with self.database.transaction() as connection:
            try:
                connection.execute(
                    "INSERT INTO source_records(source_id, schema_version, case_id, task_id, source_type, internal_path, allowed_root, allowed_root_id, metadata_json, fingerprint_json, access_status, requires_reselection, last_verified_at, revision, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
        return {"internal_path": str(row[0]), "allowed_root": str(row[1])}

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
        valid = _source_is_current(row, current_fingerprint)
        status = "available" if valid else "requires_reselection"
        source_revision = int(row["revision"])
        with self.database.transaction() as transaction:
            updated = transaction.execute(
                "UPDATE source_records SET access_status = ?, requires_reselection = ?, last_verified_at = ?, revision = revision + 1, updated_at = ? WHERE source_id = ? AND revision = ?",
                (status, bool_int(not valid), utc_now(), utc_now(), source_id, source_revision),
            )
            if updated.rowcount != 1:
                raise WorkbenchPersistenceError("SOURCE_REVISION_CONFLICT")
        return self.get(source_id)


def _source_is_current(row: Mapping[str, Any], current_fingerprint: str | None) -> bool:
    try:
        candidate = Path(str(row["internal_path"]))
        root = Path(str(row["allowed_root"]))
        resolved_candidate = candidate.resolve(strict=True)
        resolved_root = root.resolve(strict=True)
        resolved_candidate.relative_to(resolved_root)
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
