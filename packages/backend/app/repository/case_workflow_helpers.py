"""Small persistence helpers used by the case workflow repository."""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from typing import Any

from .workbench_errors import WorkbenchPersistenceError
from .workbench_serialization import validate_opaque_id, validate_safe_string


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
