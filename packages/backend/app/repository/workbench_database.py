"""SQLite initialization, migrations, transactions, and deployment isolation."""

from __future__ import annotations

import re
import sqlite3
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .workbench_constants import WORKBENCH_DATABASE_SCHEMA_VERSION
from .workbench_errors import SchemaIncompatibleError, WorkbenchPersistenceError
from .workbench_schema import MIGRATIONS, validate_schema

_DEPLOYMENT_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_utc(value: str | None) -> str:
    if value is None:
        return utc_now()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("naive timestamp")
        return parsed.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError) as error:
        raise WorkbenchPersistenceError("UTC_TIMESTAMP_REQUIRED") from error


def normalize_optional_utc(value: str | None) -> str | None:
    return None if value is None else normalize_utc(value)


def default_workbench_data_root() -> Path:
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
            connection.commit()
        except SchemaIncompatibleError:
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
