"""部署级持久保留策略基础。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .retention_policy_config import RetentionPolicyConfig, parse_retention_environment
from .retention_repository_helpers import identifier, optional_time, required_time
from ..workbench.workbench_constants import (
    RETENTION_CONFIG_BATCH_SIZE_KEY,
    RETENTION_CONFIG_DAYS_KEY,
    RETENTION_CONFIG_MODE_KEY,
    RETENTION_CONFIG_SCAN_INTERVAL_KEY,
    RETENTION_POLICY_MODES,
)
from ..workbench.workbench_database import WorkbenchDatabase, utc_now_z
from ..workbench.workbench_errors import WorkbenchPersistenceError


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

    def sync_from_environment(self, environ: Mapping[str, str]) -> dict[str, Any]:
        """将显式的规范部署设置应用到持久记录。

        这是运维人员或引导程序的边界。记录一旦存在，旧版设置便不会传给解析器，
        普通读取也绝不查询进程环境状态。
        """
        if not _has_canonical_input(environ):
            return self.get()
        parsed = parse_retention_environment(environ)
        if not parsed.valid:
            raise WorkbenchPersistenceError(parsed.diagnostic_code or "RETENTION_CONFIG_INVALID")

        with self.database.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM case_retention_policies WHERE deployment_instance_id=?",
                (self.database.deployment_instance_id,),
            ).fetchone()
            if row is None:
                raise WorkbenchPersistenceError("RETENTION_POLICY_NOT_FOUND")
            if _policy_matches(row, parsed):
                return _policy_dict(row)
            revision = int(row["policy_revision"]) + 1
            now = utc_now_z()
            updated = connection.execute(
                "UPDATE case_retention_policies SET mode=?,retention_days=?,"
                "scan_interval_seconds=?,batch_size=?,policy_revision=?,activated_at=?,updated_at=? "
                "WHERE deployment_instance_id=? AND policy_revision=?",
                (parsed.mode, parsed.retention_days, parsed.scan_interval_seconds,
                 parsed.batch_size, revision, now, now,
                 self.database.deployment_instance_id, int(row["policy_revision"])),
            )
            if updated.rowcount != 1:
                raise WorkbenchPersistenceError("RETENTION_POLICY_STALE")
            refreshed = connection.execute(
                "SELECT * FROM case_retention_policies WHERE deployment_instance_id=?",
                (self.database.deployment_instance_id,),
            ).fetchone()
        return _policy_dict(refreshed)

    def create_for_test(self, value: Mapping[str, Any]) -> dict[str, Any]:
        """持久化已验证策略，不运行协调器。"""
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


def _has_canonical_input(environ: Mapping[str, str]) -> bool:
    return any(key in environ for key in (
        RETENTION_CONFIG_MODE_KEY,
        RETENTION_CONFIG_DAYS_KEY,
        RETENTION_CONFIG_SCAN_INTERVAL_KEY,
        RETENTION_CONFIG_BATCH_SIZE_KEY,
    ))


def _policy_matches(row: Mapping[str, Any], parsed: RetentionPolicyConfig) -> bool:
    return (
        row["mode"] == parsed.mode
        and int(row["retention_days"]) == parsed.retention_days
        and int(row["scan_interval_seconds"]) == parsed.scan_interval_seconds
        and int(row["batch_size"]) == parsed.batch_size
    )
