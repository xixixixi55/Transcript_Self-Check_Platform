"""用于从 v11 迁移到 v12 的 ReportProfile 持久化结构。"""

from __future__ import annotations


V12_MIGRATION: tuple[str, ...] = (
    "CREATE TABLE report_profiles ("
    "profile_id TEXT NOT NULL, version INTEGER NOT NULL, schema_version INTEGER NOT NULL, "
    "display_name TEXT NOT NULL, structure_fingerprint TEXT NOT NULL, "
    "adapter_id TEXT NOT NULL, adapter_version TEXT NOT NULL, status TEXT NOT NULL "
    "CHECK(status IN ('draft', 'confirmed', 'retired')), mappings_json TEXT NOT NULL, "
    "created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
    "PRIMARY KEY(profile_id, version))",
    "CREATE UNIQUE INDEX report_profile_confirmed_structure "
    "ON report_profiles(structure_fingerprint) WHERE status = 'confirmed'",
    "CREATE INDEX report_profile_history ON report_profiles(profile_id, version DESC)",
)
