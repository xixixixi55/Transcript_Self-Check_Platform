"""Single-active-case edit leases with heartbeat and expired takeover."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

from .workbench_constants import LEASE_STATUSES, LEASE_TIMEOUT_SECONDS
from .workbench_database import WorkbenchDatabase
from .workbench_errors import LeaseConflictError, RevisionConflictError, WorkbenchPersistenceError
from .workbench_serialization import validate_opaque_id


class EditLeaseRepository:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database

    def acquire(
        self,
        *,
        case_id: str,
        lease_id: str,
        lease_token: str,
        identity: Mapping[str, Any],
        now: datetime | None = None,
        force_takeover: bool = False,
    ) -> dict[str, Any]:
        case_id = validate_opaque_id(case_id)
        lease_id = validate_opaque_id(lease_id)
        lease_token = validate_opaque_id(lease_token)
        validate_opaque_id(identity.get("session_id"))
        validate_opaque_id(identity.get("client_instance_id"))
        if identity.get("identity_kind") != "local_session":
            raise WorkbenchPersistenceError("UNAUTHENTICATED_IDENTITY_REQUIRED")
        if identity.get("deployment_instance_id") != self.database.deployment_instance_id:
            raise WorkbenchPersistenceError("DEPLOYMENT_INSTANCE_MISMATCH")
        current_time = _utc(now)
        expires = current_time + timedelta(seconds=LEASE_TIMEOUT_SECONDS)
        takeover_of: str | None = None
        with self.database.transaction() as connection:
            active = connection.execute(
                "SELECT * FROM edit_leases WHERE case_id = ? AND status = 'active'", (case_id,)
            ).fetchone()
            if active is not None:
                if _parse_time(str(active["expires_at"])) > current_time:
                    raise LeaseConflictError()
                if not force_takeover:
                    raise WorkbenchPersistenceError("LEASE_TAKEOVER_REQUIRED")
                takeover_of = str(active["lease_id"])
                cursor = connection.execute(
                    "UPDATE edit_leases SET status = 'expired', revision = revision + 1 "
                    "WHERE lease_id = ? AND revision = ? AND status = 'active'",
                    (takeover_of, int(active["revision"])),
                )
                if cursor.rowcount != 1:
                    raise RevisionConflictError("lease", int(active["revision"]), int(active["revision"]))
            connection.execute(
                "INSERT INTO edit_leases(lease_id, schema_version, case_id, session_id, client_instance_id, lease_token, last_heartbeat_at, expires_at, status, takeover_of_lease_id, revision) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, 0)",
                (lease_id, 1, case_id, identity["session_id"], identity["client_instance_id"], lease_token, current_time.isoformat(), expires.isoformat(), takeover_of),
            )
        return self.get(lease_id)

    def heartbeat(self, lease_id: str, lease_token: str, *, now: datetime | None = None) -> dict[str, Any]:
        lease_id = validate_opaque_id(lease_id)
        lease_token = validate_opaque_id(lease_token)
        current_time = _utc(now)
        expired = False
        with self.database.transaction() as connection:
            row = connection.execute("SELECT * FROM edit_leases WHERE lease_id = ?", (lease_id,)).fetchone()
            if row is None or row["lease_token"] != lease_token or row["status"] != "active":
                raise WorkbenchPersistenceError("LEASE_NOT_ACTIVE")
            if _parse_time(str(row["expires_at"])) <= current_time:
                cursor = connection.execute(
                    "UPDATE edit_leases SET status = 'expired', revision = revision + 1 "
                    "WHERE lease_id = ? AND revision = ? AND lease_token = ? AND status = 'active'",
                    (lease_id, int(row["revision"]), lease_token),
                )
                if cursor.rowcount != 1:
                    raise RevisionConflictError("lease", int(row["revision"]), int(row["revision"]))
                expired = True
            else:
                expires = current_time + timedelta(seconds=LEASE_TIMEOUT_SECONDS)
                cursor = connection.execute(
                    "UPDATE edit_leases SET last_heartbeat_at = ?, expires_at = ?, revision = revision + 1 "
                    "WHERE lease_id = ? AND revision = ? AND lease_token = ? AND status = 'active'",
                    (current_time.isoformat(), expires.isoformat(), lease_id, int(row["revision"]), lease_token),
                )
                if cursor.rowcount != 1:
                    raise RevisionConflictError("lease", int(row["revision"]), int(row["revision"]))
        if expired:
            raise WorkbenchPersistenceError("LEASE_EXPIRED")
        return self.get(lease_id)

    def release(self, lease_id: str, lease_token: str, expected_revision: int | None = None) -> dict[str, Any]:
        lease_id = validate_opaque_id(lease_id)
        lease_token = validate_opaque_id(lease_token)
        with self.database.transaction() as connection:
            row = connection.execute("SELECT * FROM edit_leases WHERE lease_id = ?", (lease_id,)).fetchone()
            if row is None or row["lease_token"] != lease_token:
                raise WorkbenchPersistenceError("LEASE_NOT_FOUND")
            actual = int(row["revision"])
            if row["status"] != "active":
                raise WorkbenchPersistenceError("LEASE_NOT_ACTIVE")
            if expected_revision is not None and actual != expected_revision:
                raise RevisionConflictError("lease", expected_revision, actual)
            cursor = connection.execute(
                "UPDATE edit_leases SET status = 'released', revision = revision + 1 "
                "WHERE lease_id = ? AND revision = ? AND lease_token = ? AND status = 'active'",
                (lease_id, actual, lease_token),
            )
            if cursor.rowcount != 1:
                raise RevisionConflictError("lease", actual, actual)
        return self.get(lease_id)

    def get(self, lease_id: str) -> dict[str, Any]:
        lease_id = validate_opaque_id(lease_id)
        connection = self.database.connect()
        try:
            row = connection.execute("SELECT * FROM edit_leases WHERE lease_id = ?", (lease_id,)).fetchone()
        finally:
            connection.close()
        if row is None:
            raise WorkbenchPersistenceError("LEASE_NOT_FOUND")
        if row["status"] not in LEASE_STATUSES:
            raise WorkbenchPersistenceError("INVALID_LEASE_STATUS")
        return {
            "schema_version": int(row["schema_version"]), "lease_id": row["lease_id"], "case_id": row["case_id"], "session_id": row["session_id"],
            "client_instance_id": row["client_instance_id"], "lease_token": row["lease_token"],
            "last_heartbeat_at": row["last_heartbeat_at"], "expires_at": row["expires_at"],
            "status": row["status"], "takeover_of_lease_id": row["takeover_of_lease_id"],
            "revision": int(row["revision"]),
        }

    def expire_active_after_restart(self) -> list[str]:
        with self.database.transaction() as connection:
            rows = connection.execute(
                "SELECT lease_id FROM edit_leases WHERE status = 'active'",
            ).fetchall()
            if rows:
                connection.execute(
                    "UPDATE edit_leases SET status = 'expired', revision = revision + 1 WHERE status = 'active'",
                )
        return [str(row[0]) for row in rows]

    def assert_active_for_case(
        self, case_id: str, lease_id: str, lease_token: str,
        now: datetime | None = None,
    ) -> None:
        case_id = validate_opaque_id(case_id)
        lease_id = validate_opaque_id(lease_id)
        lease_token = validate_opaque_id(lease_token)
        current_time = _utc(now)
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT status, case_id, lease_token, expires_at, revision FROM edit_leases WHERE lease_id = ?",
                (lease_id,),
            ).fetchone()
            if row is None or row["case_id"] != case_id or row["lease_token"] != lease_token:
                raise WorkbenchPersistenceError("LEASE_NOT_ACTIVE")
            if row["status"] != "active":
                raise WorkbenchPersistenceError("LEASE_NOT_ACTIVE")
            if _parse_time(str(row["expires_at"])) <= current_time:
                connection.execute(
                    "UPDATE edit_leases SET status = 'expired', revision = revision + 1 WHERE lease_id = ? AND revision = ? AND status = 'active'",
                    (lease_id, int(row["revision"])),
                )
                raise WorkbenchPersistenceError("LEASE_EXPIRED")


def _utc(value: datetime | None) -> datetime:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise WorkbenchPersistenceError("UTC_TIMESTAMP_REQUIRED")
    current = value or datetime.now(timezone.utc)
    return current.astimezone(timezone.utc)


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise WorkbenchPersistenceError("UTC_TIMESTAMP_REQUIRED")
    return parsed.astimezone(timezone.utc)
