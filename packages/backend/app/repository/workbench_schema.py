"""Layer 20: versioned SQLite schema declarations and integrity validation."""

from __future__ import annotations

import sqlite3

from .workbench_errors import SchemaIncompatibleError

REQUIRED_SCHEMA = {
    "schema_migrations": {"version", "applied_at"},
    "case_shells": {"case_id", "schema_version", "case_number", "case_name", "case_summary", "source_id", "parse_task_id", "lifecycle", "report_available", "revision", "created_at", "updated_at"},
    "case_drafts": {"case_id", "schema_version", "report_json", "report_version", "field_states_json", "asset_refs_json", "template_ref_json", "archive_plan_id", "lifecycle", "revision", "created_at", "updated_at"},
    "source_records": {"source_id", "schema_version", "case_id", "task_id", "source_type", "internal_path", "allowed_root", "allowed_root_id", "metadata_json", "fingerprint_json", "access_status", "requires_reselection", "revalidation_error_code", "last_verified_at", "revision", "created_at", "updated_at"},
    "shared_defaults": {"deployment_instance_id", "schema_version", "revision", "values_json", "migration_decision", "updated_at"},
    "task_records": {"task_id", "schema_version", "case_id", "kind", "status", "stage", "percent", "counters_json", "input_revision", "attempt", "process_binding_json", "error_code", "error_summary", "cancel_requested", "created_at", "started_at", "updated_at", "finished_at", "progress_kind", "stage_label", "stage_index", "stage_count", "last_heartbeat_at", "output_bytes", "output_volume_count", "last_output_change_at", "worker_state", "allowed_actions_json", "revision"},
    "edit_leases": {"lease_id", "schema_version", "case_id", "session_id", "client_instance_id", "lease_token", "last_heartbeat_at", "expires_at", "status", "takeover_of_lease_id", "revision"},
    "asset_references": {"asset_id", "case_id", "asset_kind", "fingerprint", "metadata_json", "status", "created_at"},
    "audit_events": {"event_id", "event_type", "deployment_instance_id", "client_instance_id", "session_id", "local_display_name", "identity_kind", "case_id", "task_id", "payload_json", "created_at"},
    "archive_attempts": {"attempt_id", "schema_version", "case_id", "source_id", "input_revision", "source_revision", "draft_revision", "report_fingerprint", "status", "cleanup_status", "error_code", "manifest_id", "manifest_source_key", "manifest_input_fingerprint", "manifest_archive_fingerprint", "staging_root_id", "staging_locator", "ownership_marker_token", "process_pid", "process_started_at", "created_at", "started_at", "finished_at", "revision"},
    "archive_context_bindings": {"context_hash", "attempt_id", "case_id", "source_id", "source_revision", "draft_revision", "report_fingerprint", "context_kind", "active", "expires_at", "consumed_at", "created_at"},
    "archive_publish_intents": {"intent_id", "attempt_id", "case_id", "source_id", "source_revision", "draft_revision", "report_fingerprint", "source_key", "input_fingerprint", "archive_fingerprint", "manifest_id", "relative_final_dir", "public_manifest_json", "fence_id", "phase", "created_at", "updated_at"},
    "archive_publish_fences": {"fence_id", "attempt_id", "case_id", "source_id", "source_revision", "draft_revision", "report_fingerprint", "context_hash", "shell_revision", "status", "reason", "created_at", "updated_at"},
    "archive_plans": {"plan_id", "schema_version", "case_id", "plan_revision", "input_inventory_revision", "mapping_revision", "volume_slots_json", "verified_slots_json", "created_at", "updated_at", "revision"},
    "archive_assets": {"asset_id", "schema_version", "case_id", "task_id", "plan_id", "asset_kind", "status", "internal_locator", "metadata_json", "created_at", "updated_at", "revision"},
    "template_versions": {"template_id", "version", "schema_version", "display_name", "fingerprint", "validation_rules_json", "asset_id", "internal_locator", "registered_at"},
    "template_approvals": {"approval_record_id", "template_id", "version", "status", "acceptance_summary", "recorded_at"},
}

MIGRATIONS: tuple[tuple[int, tuple[str, ...]], ...] = (
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
    (3, (
        "ALTER TABLE archive_attempts ADD COLUMN manifest_source_key TEXT",
        "ALTER TABLE archive_attempts ADD COLUMN manifest_input_fingerprint TEXT",
        "ALTER TABLE archive_attempts ADD COLUMN manifest_archive_fingerprint TEXT",
        "CREATE TABLE archive_context_bindings (context_hash TEXT PRIMARY KEY, attempt_id TEXT NOT NULL REFERENCES archive_attempts(attempt_id), case_id TEXT NOT NULL REFERENCES case_shells(case_id), active INTEGER NOT NULL CHECK(active IN (0, 1)), created_at TEXT NOT NULL)",
        "CREATE INDEX archive_context_attempt ON archive_context_bindings(attempt_id, active)",
    )),
    (4, (
        "ALTER TABLE archive_attempts ADD COLUMN source_revision INTEGER",
        "ALTER TABLE archive_attempts ADD COLUMN draft_revision INTEGER",
        "ALTER TABLE archive_attempts ADD COLUMN report_fingerprint TEXT",
        "UPDATE archive_attempts SET source_revision = input_revision WHERE source_revision IS NULL",
        "UPDATE archive_attempts SET draft_revision = 0 WHERE draft_revision IS NULL",
        "UPDATE archive_attempts SET report_fingerprint = '' WHERE report_fingerprint IS NULL",
        "ALTER TABLE archive_context_bindings ADD COLUMN source_id TEXT",
        "ALTER TABLE archive_context_bindings ADD COLUMN source_revision INTEGER",
        "ALTER TABLE archive_context_bindings ADD COLUMN draft_revision INTEGER",
        "ALTER TABLE archive_context_bindings ADD COLUMN report_fingerprint TEXT",
        "ALTER TABLE archive_context_bindings ADD COLUMN context_kind TEXT NOT NULL DEFAULT 'workbench'",
        "ALTER TABLE archive_context_bindings ADD COLUMN expires_at TEXT",
        "ALTER TABLE archive_context_bindings ADD COLUMN consumed_at TEXT",
        "CREATE TABLE archive_publish_intents (intent_id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL UNIQUE REFERENCES archive_attempts(attempt_id), case_id TEXT NOT NULL REFERENCES case_shells(case_id), source_id TEXT NOT NULL REFERENCES source_records(source_id), source_revision INTEGER NOT NULL, draft_revision INTEGER NOT NULL, report_fingerprint TEXT NOT NULL, source_key TEXT NOT NULL, input_fingerprint TEXT NOT NULL, archive_fingerprint TEXT NOT NULL, manifest_id TEXT NOT NULL, relative_final_dir TEXT NOT NULL, public_manifest_json TEXT NOT NULL, phase TEXT NOT NULL CHECK(phase IN ('intent_persisted', 'published', 'indexed', 'verified', 'conflict')), created_at TEXT NOT NULL, updated_at TEXT NOT NULL)",
        "CREATE INDEX archive_publish_attempt ON archive_publish_intents(attempt_id, phase)",
    )),
    (5, (
        "ALTER TABLE archive_publish_intents ADD COLUMN fence_id TEXT",
        "CREATE TABLE archive_publish_fences (fence_id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL UNIQUE REFERENCES archive_attempts(attempt_id), case_id TEXT NOT NULL REFERENCES case_shells(case_id), source_id TEXT NOT NULL REFERENCES source_records(source_id), source_revision INTEGER NOT NULL, draft_revision INTEGER NOT NULL, report_fingerprint TEXT NOT NULL, context_hash TEXT NOT NULL, shell_revision INTEGER NOT NULL, status TEXT NOT NULL CHECK(status IN ('active', 'pending_verification', 'consumed', 'released', 'invalidated')), reason TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)",
        "CREATE UNIQUE INDEX archive_publish_fence_active_case ON archive_publish_fences(case_id) WHERE status = 'active'",
        "CREATE UNIQUE INDEX archive_publish_fence_active_attempt ON archive_publish_fences(attempt_id) WHERE status = 'active'",
        "CREATE INDEX archive_publish_fence_reconciliation ON archive_publish_fences(status, attempt_id)",
    )),
    (6, (
        "ALTER TABLE task_records ADD COLUMN updated_at TEXT",
        "ALTER TABLE task_records ADD COLUMN progress_kind TEXT",
        "ALTER TABLE task_records ADD COLUMN stage_label TEXT",
        "ALTER TABLE task_records ADD COLUMN stage_index INTEGER",
        "ALTER TABLE task_records ADD COLUMN stage_count INTEGER",
        "ALTER TABLE task_records ADD COLUMN last_heartbeat_at TEXT",
        "ALTER TABLE task_records ADD COLUMN output_bytes INTEGER",
        "ALTER TABLE task_records ADD COLUMN output_volume_count INTEGER",
        "ALTER TABLE task_records ADD COLUMN last_output_change_at TEXT",
        "ALTER TABLE task_records ADD COLUMN worker_state TEXT",
        "ALTER TABLE task_records ADD COLUMN allowed_actions_json TEXT NOT NULL DEFAULT '[]'",
        "UPDATE task_records SET updated_at = COALESCE(finished_at, started_at, created_at)",
        "CREATE TABLE archive_plans (plan_id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL, case_id TEXT NOT NULL REFERENCES case_shells(case_id), plan_revision INTEGER NOT NULL, input_inventory_revision INTEGER NOT NULL, mapping_revision INTEGER NOT NULL, volume_slots_json TEXT NOT NULL, verified_slots_json TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL)",
        "CREATE INDEX archive_plan_case_revision ON archive_plans(case_id, plan_revision DESC)",
        "CREATE TABLE archive_assets (asset_id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL, case_id TEXT NOT NULL, task_id TEXT, plan_id TEXT, asset_kind TEXT NOT NULL, status TEXT NOT NULL, internal_locator TEXT, metadata_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL)",
        "CREATE INDEX archive_task_current ON task_records(case_id, kind, status, updated_at DESC)",
        "CREATE INDEX archive_asset_task ON archive_assets(task_id, status)",
    )),
    (7, (
        "CREATE TABLE template_versions (template_id TEXT NOT NULL, version TEXT NOT NULL, schema_version INTEGER NOT NULL, display_name TEXT NOT NULL, fingerprint TEXT NOT NULL, validation_rules_json TEXT NOT NULL, asset_id TEXT NOT NULL UNIQUE, internal_locator TEXT NOT NULL, registered_at TEXT NOT NULL, PRIMARY KEY(template_id, version))",
        "CREATE TABLE template_approvals (approval_record_id TEXT PRIMARY KEY, template_id TEXT NOT NULL, version TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('pending', 'approved', 'rejected', 'revoked')), acceptance_summary TEXT NOT NULL, recorded_at TEXT NOT NULL, FOREIGN KEY(template_id, version) REFERENCES template_versions(template_id, version))",
        "CREATE INDEX template_approval_history ON template_approvals(template_id, version, recorded_at DESC, approval_record_id DESC)",
    )),
)

REQUIRED_INDEXES = {
    "active_case_lease", "task_case_status", "source_case", "archive_attempt_case_status",
    "archive_context_attempt", "archive_publish_attempt", "archive_publish_fence_active_case",
    "archive_publish_fence_active_attempt", "archive_publish_fence_reconciliation",
    "archive_plan_case_revision", "archive_task_current", "archive_asset_task",
    "template_approval_history",
}


def validate_schema(connection: sqlite3.Connection) -> None:
    if str(connection.execute("PRAGMA integrity_check").fetchone()[0]) != "ok":
        raise SchemaIncompatibleError()
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise SchemaIncompatibleError()
    for table, required_columns in REQUIRED_SCHEMA.items():
        if connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
        ).fetchone() is None:
            raise SchemaIncompatibleError()
        columns = {
            str(column[1])
            for column in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if not required_columns.issubset(columns):
            raise SchemaIncompatibleError()
    indexes = {
        str(row[1])
        for row in connection.execute(
            "SELECT type, name FROM sqlite_master WHERE type = 'index'"
        ).fetchall()
    }
    if not REQUIRED_INDEXES.issubset(indexes):
        raise SchemaIncompatibleError()
