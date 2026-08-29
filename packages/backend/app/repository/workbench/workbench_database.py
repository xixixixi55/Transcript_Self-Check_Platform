"""SQLite 初始化、迁移、事务和部署隔离。"""

from __future__ import annotations

import re
import sqlite3
import os
import tempfile
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from ..retention.retention_policy_config import legacy_retention_days, parse_retention_environment
from .workbench_constants import WORKBENCH_DATABASE_SCHEMA_VERSION
from .workbench_errors import SchemaIncompatibleError, WorkbenchPersistenceError
from .workbench_schema import MIGRATIONS, validate_schema
from .workbench_time import normalize_optional_utc, normalize_utc, normalize_utc_z, utc_now, utc_now_z
from ..runtime.runtime_paths import get_runtime_paths

_DEPLOYMENT_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_LOGGER = logging.getLogger(__name__)

def default_workbench_data_root() -> Path:
    runtime_paths = get_runtime_paths()
    if runtime_paths.portable:
        return runtime_paths.data_root
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "文枢" / "data"
    return Path(tempfile.gettempdir()) / "biji-zijian-platform" / "data"


def database_path_for_deployment(data_root: str | Path | None, deployment_instance_id: str) -> Path:
    if not _DEPLOYMENT_ID.fullmatch(deployment_instance_id):
        raise ValueError("invalid deployment instance")
    root = default_workbench_data_root() if data_root is None else Path(data_root)
    return root / "instances" / deployment_instance_id / "workbench.sqlite3"


class WorkbenchDatabase:
    def __init__(self, database_path: str | Path | None, deployment_instance_id: str) -> None:
        if not _DEPLOYMENT_ID.fullmatch(deployment_instance_id):
            raise ValueError("invalid deployment instance")
        self.database_path = database_path_for_deployment(None, deployment_instance_id) if database_path is None else Path(database_path)
        self.deployment_instance_id = deployment_instance_id
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(str(self.database_path), timeout=5, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 5000")
            journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).casefold()
            if journal_mode != "delete":
                connection.close()
                connection = None
                raise SchemaIncompatibleError()
            return connection
        except SchemaIncompatibleError:
            if connection is not None:
                connection.close()
            raise
        except sqlite3.DatabaseError as error:
            if connection is not None:
                connection.close()
            raise WorkbenchPersistenceError("SQLITE_CORRUPTED") from error

    def initialize(self) -> None:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            current = int(connection.execute("PRAGMA user_version").fetchone()[0])
            was_v10_upgrade = current == 10
            migration_table = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'"
            ).fetchone()
            if not migration_table and current != 0:
                raise SchemaIncompatibleError()
            applied = {
                int(row[0]) for row in connection.execute("SELECT version FROM schema_migrations")
            } if migration_table else set()
            if current > WORKBENCH_DATABASE_SCHEMA_VERSION or any(v > WORKBENCH_DATABASE_SCHEMA_VERSION for v in applied):
                raise SchemaIncompatibleError()
            if migration_table and (not applied or current != max(applied) or sorted(applied) != list(range(1, max(applied) + 1))):
                raise SchemaIncompatibleError()
            for version, statements in MIGRATIONS:
                if version in applied:
                    continue
                for statement in statements:
                    connection.execute(statement)
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, utc_now()),
                )
            connection.execute(f"PRAGMA user_version = {WORKBENCH_DATABASE_SCHEMA_VERSION}")
            validate_schema(connection)
            owner = connection.execute(
                "SELECT deployment_instance_id FROM workbench_deployment_owner WHERE owner_id=1",
            ).fetchone()
            if owner is None:
                connection.execute(
                    "INSERT INTO workbench_deployment_owner(owner_id, deployment_instance_id, claimed_at) "
                    "VALUES (1, ?, ?)",
                    (self.deployment_instance_id, utc_now()),
                )
            elif owner["deployment_instance_id"] != self.deployment_instance_id:
                raise WorkbenchPersistenceError("WORKBENCH_DEPLOYMENT_OWNER_MISMATCH")
            _migrate_legacy_archive_identity(connection, self.deployment_instance_id)
            _ensure_deployment_identity(connection, self.deployment_instance_id)
            _ensure_initial_retention_policy(connection, self.deployment_instance_id, was_v10_upgrade)
            connection.commit()
        except SchemaIncompatibleError:
            connection.rollback()
            raise
        except WorkbenchPersistenceError:
            connection.rollback()
            raise
        except sqlite3.DatabaseError as error:
            connection.rollback()
            if "no such table" in str(error).casefold() or "duplicate column" in str(error).casefold():
                raise SchemaIncompatibleError() from error
            raise WorkbenchPersistenceError("SQLITE_CORRUPTED") from error
        finally:
            connection.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def schema_version(self) -> int:
        connection = self.connect()
        try:
            return int(connection.execute("PRAGMA user_version").fetchone()[0])
        finally:
            connection.close()

    def table_names(self) -> set[str]:
        connection = self.connect()
        try:
            rows = connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
            return {str(row[0]) for row in rows}
        finally:
            connection.close()


def _migrate_legacy_archive_identity(connection: sqlite3.Connection, deployment_id: str) -> None:
    """为任务前记录提供显式的尝试绑定兼容标识。"""
    connection.execute(
        "UPDATE task_records SET deployment_instance_id=? WHERE deployment_instance_id IS NULL",
        (deployment_id,),
    )
    connection.execute(
        "UPDATE archive_attempts SET deployment_instance_id=?, "
        "task_id=COALESCE(task_id, 'legacy-task-' || attempt_id) "
        "WHERE deployment_instance_id IS NULL OR task_id IS NULL",
        (deployment_id,),
    )
    connection.execute(
        "UPDATE archive_publish_intents SET deployment_instance_id=?, "
        "task_id=COALESCE(task_id, 'legacy-task-' || attempt_id), "
        "publication_id=COALESCE(publication_id, 'publication-' || attempt_id || '-' || manifest_id), "
        "publication_relative_dir=COALESCE(publication_relative_dir, relative_final_dir), "
        "publication_status=CASE WHEN task_id IS NULL OR publication_id IS NULL "
        "OR publication_status IS NULL THEN 'conflict' ELSE publication_status END, "
        "phase=CASE WHEN task_id IS NULL OR publication_id IS NULL "
        "OR publication_status IS NULL THEN 'conflict' ELSE phase END "
        "WHERE deployment_instance_id IS NULL OR task_id IS NULL OR publication_id IS NULL",
        (deployment_id,),
    )
    connection.execute(
        "UPDATE archive_publish_fences SET deployment_instance_id=?, "
        "task_id=COALESCE(task_id, (SELECT task_id FROM archive_attempts a "
        "WHERE a.attempt_id=archive_publish_fences.attempt_id)) "
        "WHERE deployment_instance_id IS NULL OR task_id IS NULL",
        (deployment_id,),
    )


def _ensure_deployment_identity(connection: sqlite3.Connection, deployment_id: str) -> None:
    connection.execute(
        "UPDATE case_shells SET deployment_instance_id=? WHERE deployment_instance_id IS NULL",
        (deployment_id,),
    )
    connection.execute(
        "UPDATE source_records SET deployment_instance_id=? WHERE deployment_instance_id IS NULL",
        (deployment_id,),
    )


def _ensure_initial_retention_policy(
    connection: sqlite3.Connection, deployment_id: str, allow_legacy_days: bool
) -> None:
    if connection.execute(
        "SELECT 1 FROM case_retention_policies WHERE deployment_instance_id=?",
        (deployment_id,),
    ).fetchone() is not None:
        return
    parsed = parse_retention_environment(
        os.environ,
        legacy_days=legacy_retention_days(os.environ) if allow_legacy_days else None,
        allow_legacy_days=allow_legacy_days,
    )
    if parsed.diagnostic_code:
        _LOGGER.warning(parsed.diagnostic_code)
    now = utc_now_z()
    # 全新安装和 v10 升级绝不会启动可执行的保留任务。
    connection.execute(
        "INSERT INTO case_retention_policies(deployment_instance_id,mode,retention_days,"
        "scan_interval_seconds,batch_size,policy_revision,activated_at,created_at,updated_at) "
        "VALUES (?, 'disabled', ?, ?, ?, 1, NULL, ?, ?)",
        (deployment_id, parsed.retention_days, parsed.scan_interval_seconds, parsed.batch_size, now, now),
    )
