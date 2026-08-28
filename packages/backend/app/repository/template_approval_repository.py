"""不可变模板批准历史和当前状态查询。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .template_registry_repository import TemplateRegistryRepository
from .workbench_database import WorkbenchDatabase, normalize_utc
from .workbench_errors import WorkbenchPersistenceError
from .workbench_serialization import validate_opaque_id, validate_safe_string

_STATUSES = {"pending", "approved", "rejected", "revoked"}


class TemplateApprovalRepository:
    def __init__(
        self, database: WorkbenchDatabase, registry: TemplateRegistryRepository,
    ) -> None:
        self.database = database
        self.registry = registry

    def record(
        self, template_ref: Mapping[str, Any], approval: Mapping[str, Any],
        *, connection: Any | None = None,
    ) -> dict[str, Any]:
        template = (
            self.registry.get_internal(template_ref) if connection is None
            else {"template_ref": dict(template_ref)}
        )
        value = _approval(approval)
        existing = None if connection is not None else self.find(value["approval_record_id"])
        if existing is not None:
            if existing != value | {"template_ref": template["template_ref"]}:
                raise WorkbenchPersistenceError("TEMPLATE_APPROVAL_IMMUTABLE")
            return existing
        if connection is not None:
            self._insert(connection, template, value)
            return value | {"template_ref": template["template_ref"]}
        with self.database.transaction() as transaction:
            self._insert(transaction, template, value)
        return value | {"template_ref": template["template_ref"]}

    def _insert(
        self, connection: Any, template: Mapping[str, Any], value: Mapping[str, Any],
    ) -> None:
        try:
            connection.execute(
                "INSERT INTO template_approvals(approval_record_id,template_id,"
                "version,status,acceptance_summary,recorded_at) VALUES (?,?,?,?,?,?)",
                (
                    value["approval_record_id"],
                    template["template_ref"]["template_id"],
                    template["template_ref"]["version"], value["status"],
                    value["acceptance_summary"], value["recorded_at"],
                ),
            )
        except Exception as error:
            raise WorkbenchPersistenceError("TEMPLATE_APPROVAL_CREATE_FAILED") from error

    def find(self, approval_record_id: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM template_approvals WHERE approval_record_id=?",
                (validate_opaque_id(approval_record_id),),
            ).fetchone()
        return None if row is None else _approval_row(row)

    def get_current(self, template_ref: Mapping[str, Any]) -> dict[str, Any]:
        template = self.registry.get_internal(template_ref)
        reference = template["template_ref"]
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM template_approvals WHERE template_id=? AND version=? "
                "ORDER BY recorded_at DESC,approval_record_id DESC LIMIT 1",
                (reference["template_id"], reference["version"]),
            ).fetchone()
        if row is None:
            raise WorkbenchPersistenceError("TEMPLATE_NOT_APPROVED")
        return _approval_row(row)

    def require_approved(self, template_ref: Mapping[str, Any]) -> dict[str, Any]:
        approval = self.get_current(template_ref)
        if approval["status"] != "approved":
            raise WorkbenchPersistenceError("TEMPLATE_NOT_APPROVED")
        return approval

    def list_approved(self) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT template_id,version FROM template_versions "
                "ORDER BY registered_at,template_id,version"
            ).fetchall()
        approved = []
        for row in rows:
            reference = {"template_id": row["template_id"], "version": row["version"]}
            try:
                approval = self.require_approved(reference)
            except WorkbenchPersistenceError:
                continue
            approved.append(self.registry.public_with_approval(reference, approval))
        return approved


def _approval(value: Mapping[str, Any]) -> dict[str, str]:
    status = value.get("status")
    if status not in _STATUSES:
        raise WorkbenchPersistenceError("INVALID_TEMPLATE_APPROVAL")
    summary = validate_safe_string(
        value.get("acceptance_summary"), "INVALID_TEMPLATE_APPROVAL",
    )
    if not summary.strip():
        raise WorkbenchPersistenceError("INVALID_TEMPLATE_APPROVAL")
    return {
        "approval_record_id": validate_opaque_id(value.get("approval_record_id")),
        "status": str(status), "acceptance_summary": summary,
        "recorded_at": normalize_utc(value.get("recorded_at")),
    }


def _approval_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "approval_record_id": row["approval_record_id"],
        "template_ref": {"template_id": row["template_id"], "version": row["version"]},
        "status": row["status"], "acceptance_summary": row["acceptance_summary"],
        "recorded_at": row["recorded_at"],
    }
