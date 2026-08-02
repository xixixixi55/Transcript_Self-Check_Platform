"""Deployment-scoped durable retention policy foundation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .retention_policy_config import RetentionPolicyConfig, parse_retention_environment
from .retention_repository_helpers import identifier, optional_time, required_time
from .workbench_constants import RETENTION_POLICY_MODES
from .workbench_database import WorkbenchDatabase, utc_now_z
from .workbench_errors import WorkbenchPersistenceError


class RetentionPolicyRepository:
    def __init__(self, database: WorkbenchDatabase) -> None:
        self.database = database

    def get(self) -> dict[str, Any]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM case_retention_policies WHERE deployment_instance_id=?",
                (self.database.deployment_instance_id,),
            ).fetchone()
        if row is None:
            raise WorkbenchPersistenceError("RETENTION_POLICY_NOT_FOUND")
        return _policy_dict(row)

    def ensure_initial(
        self, environ: Mapping[str, str], *, legacy_days: str | None = None,
        allow_legacy_days: bool = False,
    ) -> dict[str, Any]:
        parsed = parse_retention_environment(
            environ, legacy_days=legacy_days, allow_legacy_days=allow_legacy_days,
        )
        now = utc_now_z()
        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM case_retention_policies WHERE deployment_instance_id=?",
                (self.database.deployment_instance_id,),
            ).fetchone()
            if row is None:
                connection.execute(
                    "INSERT INTO case_retention_policies(deployment_instance_id,mode,retention_days,"
                    "scan_interval_seconds,batch_size,policy_revision,activated_at,created_at,updated_at) "
                    "VALUES (?, 'disabled', ?, ?, ?, 1, NULL, ?, ?)",
                    (self.database.deployment_instance_id, parsed.retention_days,
                     parsed.scan_interval_seconds, parsed.batch_size, now, now),
                )
                row = connection.execute(
                    "SELECT * FROM case_retention_policies WHERE deployment_instance_id=?",
                    (self.database.deployment_instance_id,),
                ).fetchone()
        return _policy_dict(row)

    def create_for_test(self, value: Mapping[str, Any]) -> dict[str, Any]:
        """Persist an already validated policy without running a coordinator."""
        mode = value.get("mode")
        if mode not in RETENTION_POLICY_MODES:
            raise WorkbenchPersistenceError("RETENTION_CONFIG_INVALID_MODE")
        days = _bounded_int(value.get("retention_days"), 1, 3650)
        interval = _bounded_int(value.get("scan_interval_seconds"), 3600, 2**31 - 1)
        batch = _bounded_int(value.get("batch_size"), 1, 1000)
        revision = _bounded_int(value.get("policy_revision"), 1, 2**31 - 1)
        now = utc_now_z()
        activated = optional_time(value.get("activated_at"))
        with self.database.transaction() as connection:
            try:
                connection.execute(
                    "INSERT INTO case_retention_policies VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (self.database.deployment_instance_id, mode, days, interval, batch,
                     revision, activated, required_time(value.get("created_at")),
                     required_time(value.get("updated_at", now))),
                )
            except Exception as error:
                raise WorkbenchPersistenceError("RETENTION_POLICY_CREATE_FAILED") from error
        return self.get()


def _bounded_int(value: Any, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise WorkbenchPersistenceError("INVALID_RETENTION_POLICY")
    return value


def _policy_dict(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "deployment_instance_id": str(row["deployment_instance_id"]),
        "mode": str(row["mode"]), "retention_days": int(row["retention_days"]),
        "scan_interval_seconds": int(row["scan_interval_seconds"]),
        "batch_size": int(row["batch_size"]), "policy_revision": int(row["policy_revision"]),
        "activated_at": row["activated_at"], "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
