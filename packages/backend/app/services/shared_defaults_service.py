"""Deployment-scoped defaults and auditable one-time migration."""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from typing import Any

from ..repository.audit_event_repository import AuditEventRepository
from ..repository.shared_defaults_repository import SharedDefaultsRepository
from ..repository.workbench_database import WorkbenchDatabase, utc_now
from ..repository.workbench_errors import WorkbenchPersistenceError


class SharedDefaultsService:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database
        self.repository = SharedDefaultsRepository(database)
        self.audit = AuditEventRepository(database)

    def get(self) -> dict[str, Any]:
        return self.repository.get()

    def save(
        self, values: Mapping[str, Any], expected_revision: int, identity: Mapping[str, Any]
    ) -> dict[str, Any]:
        _validate_identity(self.database, identity)
        result = self.repository.save(values, expected_revision)
        self._audit("shared_defaults_changed", identity, payload={"revision": result["revision"]})
        return result

    def patch(
        self, values: Mapping[str, Any], expected_revision: int, identity: Mapping[str, Any]
    ) -> dict[str, Any]:
        _validate_identity(self.database, identity)
        result = self.repository.patch(values, expected_revision)
        if result["status"] == "updated":
            self._audit("shared_defaults_changed", identity, payload={"revision": result["defaults"]["revision"]})
        return result

    def decide_migration(
        self, decision: str, identity: Mapping[str, Any], values: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        _validate_identity(self.database, identity)
        result = self.repository.decide_migration(decision, values)
        self._audit("defaults_migration_decided", identity, payload={"decision": decision})
        return result

    def _audit(self, event_type: str, identity: Mapping[str, Any], payload: Mapping[str, Any]) -> None:
        self.audit.record({
            "event_id": f"audit-{secrets.token_hex(16)}", "event_type": event_type,
            **identity, "payload": dict(payload), "created_at": utc_now(),
        })


def _validate_identity(database: WorkbenchDatabase, identity: Mapping[str, Any]) -> None:
    if identity.get("identity_kind") != "local_session" or identity.get("deployment_instance_id") != database.deployment_instance_id:
        raise WorkbenchPersistenceError("UNAUTHENTICATED_IDENTITY_REQUIRED")
    if not isinstance(identity.get("client_instance_id"), str) or not isinstance(identity.get("session_id"), str):
        raise WorkbenchPersistenceError("INVALID_CLIENT_IDENTITY")
