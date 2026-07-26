"""Case edit lease orchestration and local-session takeover audit."""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from ..repository.audit_event_repository import AuditEventRepository
from ..repository.edit_lease_repository import EditLeaseRepository
from ..repository.workbench_database import WorkbenchDatabase, utc_now
from ..repository.workbench_errors import WorkbenchPersistenceError


class EditLeaseService:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database
        self.repository = EditLeaseRepository(database)
        self.audit = AuditEventRepository(database)

    def acquire(self, case_id: str, identity: Mapping[str, Any], force_takeover: bool = False, now: datetime | None = None) -> dict[str, Any]:
        _validate_identity(self.database, identity)
        result = self.repository.acquire(
            case_id=case_id, lease_id=f"lease-{secrets.token_hex(16)}",
            lease_token=f"token-{secrets.token_hex(24)}", identity=identity,
            force_takeover=force_takeover, now=now,
        )
        if force_takeover and result.get("takeover_of_lease_id"):
            self._audit("edit_lease_taken_over", identity, case_id, result["takeover_of_lease_id"])
        return result

    def heartbeat(self, lease_id: str, lease_token: str, now: datetime | None = None) -> dict[str, Any]:
        return self.repository.heartbeat(lease_id, lease_token, now=now)

    def get(self, lease_id: str) -> dict[str, Any]:
        return self.repository.get(lease_id)

    def release(self, lease_id: str, lease_token: str, expected_revision: int | None = None) -> dict[str, Any]:
        return self.repository.release(lease_id, lease_token, expected_revision)

    def _audit(self, event_type: str, identity: Mapping[str, Any], case_id: str, old_lease_id: str) -> None:
        self.audit.record({
            "event_id": f"audit-{secrets.token_hex(16)}", "event_type": event_type,
            **identity, "case_id": case_id, "payload": {"old_lease_id": old_lease_id}, "created_at": utc_now(),
        })


def _validate_identity(database: WorkbenchDatabase, identity: Mapping[str, Any]) -> None:
    if identity.get("identity_kind") != "local_session" or identity.get("deployment_instance_id") != database.deployment_instance_id:
        raise WorkbenchPersistenceError("UNAUTHENTICATED_IDENTITY_REQUIRED")
    if not isinstance(identity.get("client_instance_id"), str) or not isinstance(identity.get("session_id"), str):
        raise WorkbenchPersistenceError("INVALID_CLIENT_IDENTITY")
