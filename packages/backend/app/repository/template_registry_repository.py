"""具有无路径公开投影的不可变版本化模板注册表。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .workbench_database import WorkbenchDatabase, normalize_utc
from .workbench_errors import WorkbenchPersistenceError
from .workbench_repository_helpers import json_text, row_json
from .workbench_serialization import validate_opaque_id, validate_safe_string


class TemplateRegistryRepository:
    def __init__(
        self, database: WorkbenchDatabase, asset_roots: Sequence[str | Path],
    ) -> None:
        self.database = database
        self.asset_roots = tuple(Path(root).resolve() for root in asset_roots)
        if not self.asset_roots:
            raise ValueError("template asset roots are required")

    def register(
        self, template: Mapping[str, Any], asset_path: str | Path,
        *, connection: Any | None = None,
    ) -> dict[str, Any]:
        value = _template(template)
        locator = self._controlled_locator(asset_path)
        existing = self.find_internal(value["template_ref"])
        if existing is not None:
            immutable = {**_without_approval(existing), "internal_locator": existing["internal_locator"]}
            requested = {**value, "internal_locator": str(locator)}
            if immutable != requested:
                raise WorkbenchPersistenceError("TEMPLATE_VERSION_IMMUTABLE")
            return existing
        if connection is not None:
            self._insert(connection, value, locator)
            return value | {"internal_locator": str(locator)}
        with self.database.transaction() as transaction:
            self._insert(transaction, value, locator)
        return self.get_internal(value["template_ref"])

    def _insert(self, connection: Any, value: Mapping[str, Any], locator: Path) -> None:
        try:
            connection.execute(
                "INSERT INTO template_versions(template_id,version,schema_version,"
                "display_name,fingerprint,validation_rules_json,asset_id,"
                "internal_locator,registered_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    value["template_ref"]["template_id"],
                    value["template_ref"]["version"], value["schema_version"],
                    value["display_name"], value["fingerprint"],
                    json_text(value["validation_rules"]), value["asset_id"],
                    str(locator), value["registered_at"],
                ),
            )
        except Exception as error:
            if "UNIQUE constraint failed" in str(error):
                raise WorkbenchPersistenceError("TEMPLATE_VERSION_IMMUTABLE") from error
            raise WorkbenchPersistenceError("TEMPLATE_VERSION_CREATE_FAILED") from error

    def find_internal(self, template_ref: Mapping[str, Any]) -> dict[str, Any] | None:
        reference = _reference(template_ref)
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM template_versions WHERE template_id=? AND version=?",
                (reference["template_id"], reference["version"]),
            ).fetchone()
        return None if row is None else _template_row(row)

    def get_internal(self, template_ref: Mapping[str, Any]) -> dict[str, Any]:
        value = self.find_internal(template_ref)
        if value is None:
            raise WorkbenchPersistenceError("TEMPLATE_UNKNOWN")
        return value

    def rename_display_name(
        self, template_ref: Mapping[str, Any], display_name: str,
    ) -> dict[str, Any]:
        reference = _reference(template_ref)
        name = validate_safe_string(display_name, "TEMPLATE_NAME_INVALID").strip()
        if not name or len(name) > 120:
            raise WorkbenchPersistenceError("TEMPLATE_NAME_INVALID")
        with self.database.transaction() as connection:
            cursor = connection.execute(
                "UPDATE template_versions SET display_name=? "
                "WHERE template_id=? AND version=?",
                (name, reference["template_id"], reference["version"]),
            )
            if cursor.rowcount != 1:
                raise WorkbenchPersistenceError("TEMPLATE_UNKNOWN")
        return self.get_internal(reference)

    def relocate_builtin_asset(
        self,
        template_ref: Mapping[str, Any],
        expected_fingerprint: str,
        expected_asset_id: str,
        asset_path: str | Path,
    ) -> None:
        """服务验证资产后重新定位已知内置版本。"""
        reference = _reference(template_ref)
        existing = self.find_internal(reference)
        if existing is None:
            return
        locator = self._controlled_locator(asset_path)
        if (
            existing["fingerprint"] != expected_fingerprint
            or existing["asset_id"] != expected_asset_id
        ):
            return
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE template_versions SET internal_locator=? "
                "WHERE template_id=? AND version=? AND fingerprint=? AND asset_id=?",
                (
                    str(locator), reference["template_id"], reference["version"],
                    expected_fingerprint, expected_asset_id,
                ),
            )

    def remove_builtin_versions(
        self, template_id: str, versions: set[str] | frozenset[str],
    ) -> int:
        """引用迁移后移除已停用的内置注册表元数据。"""
        template_id = validate_opaque_id(template_id)
        normalized = tuple(sorted(validate_opaque_id(version) for version in versions))
        if not normalized:
            return 0
        placeholders = ",".join("?" for _ in normalized)
        parameters = (template_id, *normalized)
        with self.database.transaction() as connection:
            connection.execute(
                f"DELETE FROM template_approvals WHERE template_id=? AND version IN ({placeholders})",
                parameters,
            )
            removed = connection.execute(
                f"DELETE FROM template_versions WHERE template_id=? AND version IN ({placeholders})",
                parameters,
            )
        return removed.rowcount

    def public_with_approval(
        self, template_ref: Mapping[str, Any], approval: Mapping[str, Any],
    ) -> dict[str, Any]:
        value = self.get_internal(template_ref)
        public_approval = {
            key: approval[key] for key in (
                "approval_record_id", "status", "acceptance_summary", "recorded_at",
            )
        }
        return {
            key: value[key] for key in (
                "schema_version", "template_ref", "display_name", "fingerprint",
                "validation_rules", "asset_id", "registered_at",
            )
        } | {"approval_record": public_approval}

    def _controlled_locator(self, asset_path: str | Path) -> Path:
        candidate = Path(asset_path).resolve()
        if not candidate.is_file() or candidate.suffix.casefold() != ".docx":
            raise WorkbenchPersistenceError("TEMPLATE_ASSET_MISSING")
        if not any(candidate == root or root in candidate.parents for root in self.asset_roots):
            raise WorkbenchPersistenceError("TEMPLATE_ASSET_OUTSIDE_CONTROLLED_ROOT")
        return candidate


def _reference(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != {"template_id", "version"}:
        raise WorkbenchPersistenceError("INVALID_TEMPLATE_REFERENCE")
    return {
        "template_id": validate_opaque_id(value["template_id"]),
        "version": validate_opaque_id(value["version"]),
    }


def _template(value: Mapping[str, Any]) -> dict[str, Any]:
    if value.get("schema_version") != 1:
        raise WorkbenchPersistenceError("INVALID_TEMPLATE_VERSION")
    rules = value.get("validation_rules")
    if not isinstance(rules, list) or not rules:
        raise WorkbenchPersistenceError("INVALID_TEMPLATE_VERSION")
    normalized_rules = []
    for rule in rules:
        if not isinstance(rule, Mapping) or set(rule) != {"rule_id", "version"}:
            raise WorkbenchPersistenceError("INVALID_TEMPLATE_VERSION")
        normalized_rules.append({
            "rule_id": validate_opaque_id(rule["rule_id"]),
            "version": validate_opaque_id(rule["version"]),
        })
    fingerprint = validate_safe_string(value.get("fingerprint"), "INVALID_TEMPLATE_VERSION")
    if len(fingerprint) != 64 or any(char not in "0123456789ABCDEF" for char in fingerprint):
        raise WorkbenchPersistenceError("INVALID_TEMPLATE_VERSION")
    return {
        "schema_version": 1,
        "template_ref": _reference(value.get("template_ref")),
        "display_name": validate_safe_string(value.get("display_name"), "INVALID_TEMPLATE_VERSION"),
        "fingerprint": fingerprint,
        "validation_rules": normalized_rules,
        "asset_id": validate_opaque_id(value.get("asset_id")),
        "registered_at": normalize_utc(value.get("registered_at")),
    }


def _template_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": int(row["schema_version"]),
        "template_ref": {"template_id": row["template_id"], "version": row["version"]},
        "display_name": row["display_name"], "fingerprint": row["fingerprint"],
        "validation_rules": row_json(row, "validation_rules_json"),
        "asset_id": row["asset_id"], "internal_locator": row["internal_locator"],
        "registered_at": row["registered_at"],
    }


def _without_approval(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value[key] for key in (
            "schema_version", "template_ref", "display_name", "fingerprint",
            "validation_rules", "asset_id", "registered_at",
        )
    }
