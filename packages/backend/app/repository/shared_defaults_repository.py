"""Deployment-instance shared defaults with explicit revision and migration state."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .workbench_database import WorkbenchDatabase, utc_now
from .workbench_errors import RevisionConflictError, WorkbenchPersistenceError
from .workbench_repository_helpers import bool_int, json_text, row_json
from .workbench_serialization import validate_opaque_id, validate_safe_string

_DEFAULT_VALUES = {
    "document_number": "",
    "inspection_place": "",
    "inspection_method": "",
    "hardware_device": "",
    "inspector_order": [],
    "disc_number_prefix": "",
    "default_template_ref": None,
}
_MIGRATION_DECISIONS = {"pending", "imported", "ignored"}


class SharedDefaultsRepository:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database

    def get_or_create(self) -> dict[str, Any]:
        connection = self.database.connect()
        try:
            row = connection.execute(
                "SELECT * FROM shared_defaults WHERE deployment_instance_id = ?",
                (self.database.deployment_instance_id,),
            ).fetchone()
        finally:
            connection.close()
        if row is not None:
            return _defaults_dict(row)
        now = utc_now()
        with self.database.transaction() as transaction:
            transaction.execute(
                "INSERT OR IGNORE INTO shared_defaults(deployment_instance_id, schema_version, revision, values_json, migration_decision, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (self.database.deployment_instance_id, 1, 0, json_text(_DEFAULT_VALUES), "pending", now),
            )
        return self.get_or_create()

    def save(self, values: Mapping[str, Any], expected_revision: int) -> dict[str, Any]:
        normalized = _normalize_values(values)
        self.get_or_create()
        with self.database.transaction() as transaction:
            row = transaction.execute(
                "SELECT revision, migration_decision FROM shared_defaults WHERE deployment_instance_id = ?",
                (self.database.deployment_instance_id,),
            ).fetchone()
            if row is None:
                raise WorkbenchPersistenceError("DEFAULTS_NOT_FOUND")
            actual = int(row[0])
            if actual != expected_revision:
                raise RevisionConflictError("shared_defaults", expected_revision, actual)
            updated = transaction.execute(
                "UPDATE shared_defaults SET values_json = ?, revision = revision + 1, updated_at = ? WHERE deployment_instance_id = ? AND revision = ?",
                (json_text(normalized), utc_now(), self.database.deployment_instance_id, expected_revision),
            )
            if updated.rowcount != 1:
                raise RevisionConflictError("shared_defaults", expected_revision, actual)
        return self.get_or_create()

    def patch(self, values: Mapping[str, Any], expected_revision: int) -> dict[str, Any]:
        """Merge only explicitly supplied, non-empty shared default fields."""
        normalized = _normalize_patch(values)
        current = self.get_or_create()
        if not normalized:
            return {"status": "unchanged", "defaults": current, "changed_fields": []}
        with self.database.transaction() as transaction:
            row = transaction.execute(
                "SELECT revision, values_json FROM shared_defaults WHERE deployment_instance_id = ?",
                (self.database.deployment_instance_id,),
            ).fetchone()
            if row is None:
                raise WorkbenchPersistenceError("DEFAULTS_NOT_FOUND")
            actual = int(row[0])
            if actual != expected_revision:
                raise RevisionConflictError("shared_defaults", expected_revision, actual)
            merged = dict(_DEFAULT_VALUES)
            merged.update(row_json(row, "values_json") if hasattr(row, "keys") and "values_json" in row.keys() else {})
            changed = [key for key, value in normalized.items() if merged.get(key) != value]
            if not changed:
                return {"status": "unchanged", "defaults": self.get_or_create(), "changed_fields": []}
            merged.update(normalized)
            updated = transaction.execute(
                "UPDATE shared_defaults SET values_json = ?, revision = revision + 1, updated_at = ? WHERE deployment_instance_id = ? AND revision = ?",
                (json_text(merged), utc_now(), self.database.deployment_instance_id, expected_revision),
            )
            if updated.rowcount != 1:
                raise RevisionConflictError("shared_defaults", expected_revision, actual)
        return {"status": "updated", "defaults": self.get_or_create(), "changed_fields": changed}

    def decide_migration(self, decision: str, imported_values: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if decision not in _MIGRATION_DECISIONS or decision == "pending":
            raise WorkbenchPersistenceError("INVALID_DEFAULTS_MIGRATION_DECISION")
        normalized = _normalize_values(imported_values or _DEFAULT_VALUES)
        self.get_or_create()
        with self.database.transaction() as transaction:
            row = transaction.execute(
                "SELECT migration_decision FROM shared_defaults WHERE deployment_instance_id = ?",
                (self.database.deployment_instance_id,),
            ).fetchone()
            if row is None:
                raise WorkbenchPersistenceError("DEFAULTS_NOT_FOUND")
            if row[0] != "pending":
                raise WorkbenchPersistenceError("DEFAULTS_MIGRATION_ALREADY_DECIDED")
            updated = transaction.execute(
                "UPDATE shared_defaults SET values_json = ?, migration_decision = ?, revision = revision + 1, updated_at = ? WHERE deployment_instance_id = ? AND migration_decision = 'pending'",
                (json_text(normalized if decision == "imported" else _DEFAULT_VALUES), decision, utc_now(), self.database.deployment_instance_id),
            )
            if updated.rowcount != 1:
                raise WorkbenchPersistenceError("DEFAULTS_MIGRATION_ALREADY_DECIDED")
        return self.get_or_create()

    def get(self) -> dict[str, Any]:
        return self.get_or_create()

    def ensure_default_template(self, template_ref: Mapping[str, Any]) -> dict[str, Any]:
        normalized = _normalize_template_ref(template_ref)
        if normalized is None:
            raise WorkbenchPersistenceError("INVALID_TEMPLATE_REFERENCE")
        current = self.get_or_create()
        if current.get("default_template_ref") is not None:
            return current
        result = self.patch({"default_template_ref": normalized}, current["revision"])
        return result["defaults"]


def _normalize_values(values: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(values, Mapping):
        raise WorkbenchPersistenceError("INVALID_SHARED_DEFAULTS")
    normalized = dict(_DEFAULT_VALUES)
    for key in normalized:
        if key in values:
            normalized[key] = values[key]
    if not isinstance(normalized["inspector_order"], list) or any(
        not isinstance(item, str) for item in normalized["inspector_order"]
    ):
        raise WorkbenchPersistenceError("INVALID_SHARED_DEFAULTS")
    for key in ("document_number", "inspection_place", "inspection_method", "hardware_device", "disc_number_prefix"):
        validate_safe_string(normalized[key], "INVALID_SHARED_DEFAULTS")
    for item in normalized["inspector_order"]:
        validate_safe_string(item, "INVALID_SHARED_DEFAULTS")
    normalized["default_template_ref"] = _normalize_template_ref(
        normalized.get("default_template_ref"),
    )
    json_text(normalized)
    return normalized


def _normalize_patch(values: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(values, Mapping):
        raise WorkbenchPersistenceError("INVALID_SHARED_DEFAULTS")
    unknown = set(values) - set(_DEFAULT_VALUES)
    if unknown:
        raise WorkbenchPersistenceError("UNKNOWN_SHARED_DEFAULT_FIELD")
    normalized: dict[str, Any] = {}
    scalar_keys = ("document_number", "inspection_place", "inspection_method", "hardware_device", "disc_number_prefix")
    for key in scalar_keys:
        if key not in values:
            continue
        value = values[key]
        if not isinstance(value, str):
            raise WorkbenchPersistenceError("INVALID_SHARED_DEFAULTS")
        validate_safe_string(value, "INVALID_SHARED_DEFAULTS")
        if value.strip():
            normalized[key] = value.strip()
    if "inspector_order" in values:
        items = values["inspector_order"]
        if not isinstance(items, list) or any(not isinstance(item, str) for item in items):
            raise WorkbenchPersistenceError("INVALID_SHARED_DEFAULTS")
        normalized_items = [item.strip() for item in items]
        for item in normalized_items:
            validate_safe_string(item, "INVALID_SHARED_DEFAULTS")
            if not item:
                raise WorkbenchPersistenceError("INVALID_SHARED_DEFAULTS")
        if normalized_items:
            normalized["inspector_order"] = normalized_items
    if "default_template_ref" in values:
        normalized["default_template_ref"] = _normalize_template_ref(
            values["default_template_ref"],
        )
    return normalized


def _normalize_template_ref(value: Any) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping) or set(value) != {"template_id", "version"}:
        raise WorkbenchPersistenceError("INVALID_TEMPLATE_REFERENCE")
    return {
        "template_id": validate_opaque_id(value["template_id"]),
        "version": validate_opaque_id(value["version"]),
    }


def _defaults_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    values = {**_DEFAULT_VALUES, **row_json(row, "values_json")}
    return {
        "schema_version": int(row["schema_version"]),
        "deployment_instance_id": row["deployment_instance_id"],
        "revision": int(row["revision"]),
        **values,
        "migration_decision": row["migration_decision"],
        "updated_at": row["updated_at"],
    }
