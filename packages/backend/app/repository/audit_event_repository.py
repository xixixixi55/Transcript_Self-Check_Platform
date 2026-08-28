"""未经认证的本地会话审计事件。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .workbench_database import WorkbenchDatabase, normalize_utc
from .workbench_errors import WorkbenchPersistenceError
from .workbench_repository_helpers import json_text
from .workbench_serialization import validate_opaque_id, validate_safe_string


class AuditEventRepository:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database

    def record(self, event: Mapping[str, Any]) -> dict[str, Any]:
        if event.get("identity_kind") != "local_session":
            raise WorkbenchPersistenceError("UNAUTHENTICATED_IDENTITY_REQUIRED")
        event_id = validate_opaque_id(event.get("event_id"))
        deployment_instance_id = validate_opaque_id(event.get("deployment_instance_id"))
        client_instance_id = validate_opaque_id(event.get("client_instance_id"))
        session_id = validate_opaque_id(event.get("session_id"))
        if deployment_instance_id != self.database.deployment_instance_id:
            raise WorkbenchPersistenceError("DEPLOYMENT_INSTANCE_MISMATCH")
        case_id = None if event.get("case_id") is None else validate_opaque_id(event.get("case_id"))
        task_id = None if event.get("task_id") is None else validate_opaque_id(event.get("task_id"))
        event_type = validate_safe_string(event.get("event_type"), "INVALID_AUDIT_EVENT")
        local_display_name = None if event.get("local_display_name") is None else validate_safe_string(event.get("local_display_name"), "INVALID_AUDIT_EVENT")
        values = (
            event_id, event_type, deployment_instance_id,
            client_instance_id, session_id, local_display_name,
            "local_session", case_id, task_id,
            json_text(event.get("payload", {})), normalize_utc(event.get("created_at")),
        )
        with self.database.transaction() as connection:
            try:
                connection.execute(
                    "INSERT INTO audit_events(event_id, event_type, deployment_instance_id, client_instance_id, session_id, local_display_name, identity_kind, case_id, task_id, payload_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    values,
                )
            except Exception as error:
                raise WorkbenchPersistenceError("AUDIT_EVENT_CREATE_FAILED") from error
        return {
            "event_id": values[0], "event_type": values[1], "deployment_instance_id": values[2],
            "client_instance_id": values[3], "session_id": values[4], "local_display_name": values[5],
            "identity_kind": values[6], "case_id": values[7], "task_id": values[8], "created_at": values[10],
        }
