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

_DEPLOYMENT_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_REQUIRED_SCHEMA = {
    "schema_migrations": {"version", "applied_at"},
    "case_shells": {"case_id", "schema_version", "case_number", "case_name", "case_summary", "source_id", "parse_task_id", "lifecycle", "report_available", "revision", "created_at", "updated_at"},
    "case_drafts": {"case_id", "schema_version", "report_json", "report_version", "field_states_json", "asset_refs_json", "template_ref_json", "archive_plan_id", "lifecycle", "revision", "created_at", "updated_at"},
    "source_records": {"source_id", "schema_version", "case_id", "task_id", "source_type", "internal_path", "allowed_root", "allowed_root_id", "metadata_json", "fingerprint_json", "access_status", "requires_reselection", "revalidation_error_code", "last_verified_at", "revision", "created_at", "updated_at"},
    "shared_defaults": {"deployment_instance_id", "schema_version", "revision", "values_json", "migration_decision", "updated_at"},
    "task_records": {"task_id", "schema_version", "case_id", "kind", "status", "stage", "percent", "counters_json", "input_revision", "attempt", "process_binding_json", "error_code", "error_summary", "cancel_requested", "created_at", "started_at", "finished_at", "revision"},
    "edit_leases": {"lease_id", "schema_version", "case_id", "session_id", "client_instance_id", "lease_token", "last_heartbeat_at", "expires_at", "status", "takeover_of_lease_id", "revision"},
    "asset_references": {"asset_id", "case_id", "asset_kind", "fingerprint", "metadata_json", "status", "created_at"},
    "audit_events": {"event_id", "event_type", "deployment_instance_id", "client_instance_id", "session_id", "local_display_name", "identity_kind", "case_id", "task_id", "payload_json", "created_at"},
    "archive_attempts": {"attempt_id", "schema_version", "case_id", "source_id", "input_revision", "status", "cleanup_status", "error_code", "manifest_id", "staging_root_id", "staging_locator", "ownership_marker_token", "process_pid", "process_started_at", "created_at", "started_at", "finished_at", "revision"},
}

_MIGRATIONS: tuple[tuple[int, tuple[str, ...]], ...] = (
    (1, (
        "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)",
        "CREATE TABLE case_shells (case_id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL, case_number TEXT, case_name TEXT NOT NULL, case_summary TEXT NOT NULL, source_id TEXT NOT NULL, parse_task_id TEXT NOT NULL, lifecycle TEXT NOT NULL, report_available INTEGER NOT NULL CHECK(report_available IN (0, 1)), revision INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)",
        "CREATE TABLE case_drafts (case_id TEXT PRIMARY KEY REFERENCES case_shells(case_id) ON DELETE CASCADE, schema_version INTEGER NOT NULL, report_json TEXT NOT NULL, report_version TEXT NOT NULL, field_states_json TEXT NOT NULL, asset_refs_json TEXT NOT NULL, template_ref_json TEXT, archive_plan_id TEXT, lifecycle TEXT NOT NULL, revision INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)",
        "CREATE TABLE source_records (source_id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL, case_id TEXT NOT NULL REFERENCES case_shells(case_id), task_id TEXT REFERENCES task_records(task_id), source_type TEXT NOT NULL, internal_path TEXT NOT NULL, allowed_root TEXT NOT NULL, allowed_root_id TEXT NOT NULL, metadata_json TEXT NOT NULL, fingerprint_json TEXT NOT NULL, access_status TEXT NOT NULL, requires_reselection INTEGER NOT NULL CHECK(requires_reselection IN (0, 1)), last_verified_at TEXT, revision INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)",
        "CREATE TABLE shared_defaults (deployment_instance_id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL, revision INTEGER NOT NULL, values_json TEXT NOT NULL, migration_decision TEXT NOT NULL CHECK(migration_decision IN ('pending', 'imported', 'ignored')), updated_at TEXT NOT NULL)",
        "CREATE TABLE task_records (task_id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL, case_id TEXT NOT NULL REFERENCES case_shells(case_id), kind TEXT NOT NULL, status TEXT NOT NULL, stage TEXT NOT NULL, percent REAL, counters_json TEXT NOT NULL, input_revision INTEGER NOT NULL, attempt INTEGER NOT NULL, process_binding_json TEXT, error_code TEXT, error_summary TEXT, cancel_requested INTEGER NOT NULL CHECK(cancel_requested IN (0, 1)), created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT, revision INTEGER NOT NULL)",
        "CREATE TABLE edit_leases (lease_id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL, case_id TEXT NOT NULL REFERENCES case_shells(case_id) ON DELETE CASCADE, session_id TEXT NOT NULL, client_instance_id TEXT NOT NULL, lease_token TEXT NOT NULL, last_heartbeat_at TEXT NOT NULL, expires_at TEXT NOT NULL, status TEXT NOT NULL, takeover_of_lease_id TEXT, revision INTEGER NOT NULL)",
        "CREATE TABLE asset_references (asset_id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES case_shells(case_id) ON DELETE CASCADE, asset_kind TEXT NOT NULL, fingerprint TEXT, metadata_json TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL)",
        "CREATE TABLE audit_events (event_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, deployment_instance_id TEXT NOT NULL, client_instance_id TEXT NOT NULL, session_id TEXT NOT NULL, local_display_name TEXT, identity_kind TEXT NOT NULL CHECK(identity_kind = 'local_session'), case_id TEXT, task_id TEXT, payload_json TEXT NOT NULL, created_at TEXT NOT NULL)",
        "CREATE UNIQUE INDEX active_case_lease ON edit_leases(case_id) WHERE status = 'active'",
        "CREATE INDEX task_case_status ON task_records(case_id, status)",
        "CREATE INDEX source_case ON source_records(case_id)",
    )),
    (2, (
        "ALTER TABLE source_records ADD COLUMN revalidation_error_code TEXT",
        "CREATE TABLE archive_attempts (attempt_id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL, case_id TEXT NOT NULL REFERENCES case_shells(case_id), source_id TEXT NOT NULL REFERENCES source_records(source_id), input_revision INTEGER NOT NULL, status TEXT NOT NULL CHECK(status IN ('accepted', 'running', 'succeeded', 'failed', 'interrupted')), cleanup_status TEXT NOT NULL CHECK(cleanup_status IN ('not_required', 'pending', 'succeeded', 'failed', 'unknown')), error_code TEXT, manifest_id TEXT, staging_root_id TEXT, staging_locator TEXT, ownership_marker_token TEXT, process_pid INTEGER, process_started_at TEXT, created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT, revision INTEGER NOT NULL)",
        "CREATE INDEX archive_attempt_case_status ON archive_attempts(case_id, status)",
    )),
)


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
            for version, statements in _MIGRATIONS:
                if version in applied:
                    continue
                for statement in statements:
                    connection.execute(statement)
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, utc_now()),
                )
            connection.execute(f"PRAGMA user_version = {WORKBENCH_DATABASE_SCHEMA_VERSION}")
            _validate_schema(connection)
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


def _validate_schema(connection: sqlite3.Connection) -> None:
    integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
    if integrity != "ok":
        raise SchemaIncompatibleError()
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise SchemaIncompatibleError()
    for table, required_columns in _REQUIRED_SCHEMA.items():
        row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
        ).fetchone()
        if row is None:
            raise SchemaIncompatibleError()
        columns = {
            str(column[1]) for column in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if not required_columns.issubset(columns):
            raise SchemaIncompatibleError()
    indexes = {
        str(row[1]) for row in connection.execute(
            "SELECT type, name FROM sqlite_master WHERE type = 'index'"
        ).fetchall()
    }
    if not {"active_case_lease", "task_case_status", "source_case", "archive_attempt_case_status"}.issubset(indexes):
        raise SchemaIncompatibleError()
