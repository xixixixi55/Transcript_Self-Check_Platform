"""Slice 5A-1 非空 v10 图迁移与回滚证据。"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

import app.repository.workbench.workbench_database as database_module  # noqa: E402
from app.repository import WorkbenchDatabase  # noqa: E402
from app.repository.workbench.workbench_errors import WorkbenchPersistenceError  # noqa: E402
from app.repository.workbench.workbench_schema import MIGRATIONS  # noqa: E402

_DEPLOYMENT = "SYNTHETIC-MIGRATION-GRAPH"
_CASE = "SYNTHETIC-CASE-MIGRATION"
_TASK = "SYNTHETIC-TASK-MIGRATION"
_SOURCE = "SYNTHETIC-SOURCE-MIGRATION"
_ATTEMPT = "SYNTHETIC-ATTEMPT-MIGRATION"
_SNAPSHOT = "SYNTHETIC-SNAPSHOT-MIGRATION"
_FENCE = "SYNTHETIC-FENCE-MIGRATION"
_INTENT = "SYNTHETIC-INTENT-MIGRATION"
_PUBLICATION = "SYNTHETIC-PUBLICATION-MIGRATION"
_CONTEXT = "SYNTHETIC-CONTEXT-MIGRATION"
_PLAN = "SYNTHETIC-PLAN-MIGRATION"
_ASSET = "SYNTHETIC-ASSET-MIGRATION"
_WORK_ASSET = "SYNTHETIC-WORK-ASSET-MIGRATION"
_REFERENCE = _WORK_ASSET
_TIME = "2026-08-01T00:00:00Z"
_DIGEST = "a" * 64
_FILE_SET = [{"name": "SYNTHETIC.rar", "size": 10}, {"name": "SYNTHETIC.md5", "size": 32}]


def _build_v10_graph(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        for version, statements in MIGRATIONS:
            if version > 10:
                break
            for statement in statements:
                connection.execute(statement)
            connection.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (version, _TIME),
            )
        connection.execute("PRAGMA user_version = 10")
        connection.execute("INSERT INTO workbench_deployment_owner VALUES (1, ?, ?)", (_DEPLOYMENT, _TIME))
        connection.execute(
            "INSERT INTO case_shells VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (_CASE, 1, "SYNTHETIC-CASE-NO", "SYNTHETIC/CASE", "SYNTHETIC-SUMMARY", _SOURCE, _TASK,
             "archiving", 1, 2, _TIME, _TIME),
        )
        connection.execute(
            "INSERT INTO task_records(task_id,schema_version,case_id,kind,status,stage,percent,counters_json,"
            "input_revision,attempt,process_binding_json,error_code,error_summary,cancel_requested,created_at,"
            "started_at,finished_at,revision,updated_at,progress_kind,stage_label,stage_index,stage_count,"
            "last_heartbeat_at,output_bytes,output_volume_count,last_output_change_at,worker_state,"
            "allowed_actions_json,deployment_instance_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (_TASK, 1, _CASE, "archive", "succeeded", "completed", 100.0, "{}", 1, 1, None, None, None, 0,
             _TIME, _TIME, _TIME, 1, _TIME, "archive", "completed", 1, 1, _TIME, 10, 1, _TIME, "succeeded", "[]",
             _DEPLOYMENT),
        )
        connection.execute(
            "INSERT INTO source_records(source_id,schema_version,case_id,task_id,source_type,internal_path,"
            "allowed_root,allowed_root_id,metadata_json,fingerprint_json,access_status,requires_reselection,"
            "revalidation_error_code,last_verified_at,revision,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (_SOURCE, 1, _CASE, _TASK, "report_directory", "SYNTHETIC/TEST/source", "SYNTHETIC/TEST",
             "SYNTHETIC-ROOT", '{"kind":"source"}', '{"fingerprint":"source"}', "available", 0, None,
             _TIME, 1, _TIME, _TIME),
        )
        connection.execute(
            "INSERT INTO archive_plans VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (_PLAN, 1, _CASE, 1, 1, 1, '{"slots":1}', '["SYNTHETIC.rar"]', _TIME, _TIME, 1),
        )
        connection.execute(
            "INSERT INTO case_drafts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (_CASE, 1, '{"synthetic":true}', "v1", "{}", json.dumps([_REFERENCE]), '{"template":"legacy"}',
             _PLAN, "editable", 1, _TIME, _TIME),
        )
        connection.execute(
            "INSERT INTO asset_references(asset_id,case_id,asset_kind,fingerprint,metadata_json,status,created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (_REFERENCE, _CASE, "draft_attachment", "SYNTHETIC-ASSET-FP", '{"work":true}', "active", _TIME),
        )
        connection.execute(
            "INSERT INTO archive_attempts(attempt_id,schema_version,case_id,source_id,input_revision,status,"
            "cleanup_status,error_code,manifest_id,staging_root_id,staging_locator,ownership_marker_token,"
            "process_pid,process_started_at,created_at,started_at,finished_at,revision,manifest_source_key,"
            "manifest_input_fingerprint,manifest_archive_fingerprint,source_revision,draft_revision,report_fingerprint,"
            "task_id,deployment_instance_id,input_snapshot_id,input_snapshot_root_id,input_snapshot_locator,"
            "input_snapshot_fingerprint,input_snapshot_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (_ATTEMPT, 1, _CASE, _SOURCE, 1, "succeeded", "not_required", None, "SYNTHETIC-MANIFEST",
             "SYNTHETIC-STAGING", "staging/attempt", "SYNTHETIC-MARKER", None, _TIME, _TIME, _TIME, _TIME, 1,
             "SYNTHETIC-SOURCE-KEY", "SYNTHETIC-INPUT", "SYNTHETIC-ARCHIVE", 1, 1, "SYNTHETIC-REPORT", _TASK,
             _DEPLOYMENT, _SNAPSHOT, "SYNTHETIC-SNAPSHOT-ROOT", "snapshot/attempt", "SYNTHETIC-SNAPSHOT-FP", "sealed"),
        )
        connection.execute(
            "INSERT INTO archive_context_bindings(context_hash,attempt_id,case_id,active,created_at,source_id,"
            "source_revision,draft_revision,report_fingerprint,context_kind,expires_at,consumed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (_CONTEXT, _ATTEMPT, _CASE, 1, _TIME, _SOURCE, 1, 1, "SYNTHETIC-REPORT", "workbench", None, None),
        )
        connection.execute(
            "INSERT INTO archive_publish_fences(fence_id,attempt_id,task_id,deployment_instance_id,case_id,source_id,"
            "source_revision,draft_revision,report_fingerprint,context_hash,shell_revision,status,reason,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (_FENCE, _ATTEMPT, _TASK, _DEPLOYMENT, _CASE, _SOURCE, 1, 1, "SYNTHETIC-REPORT", _CONTEXT, 2,
             "consumed", "verified", _TIME, _TIME),
        )
        connection.execute(
            "INSERT INTO archive_input_snapshots(snapshot_id,task_id,attempt_id,deployment_instance_id,case_id,source_id,"
            "source_revision,draft_revision,source_root_id,snapshot_root_id,snapshot_locator,manifest_json,input_fingerprint,"
            "status,marker_token,created_at,sealed_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (_SNAPSHOT, _TASK, _ATTEMPT, _DEPLOYMENT, _CASE, _SOURCE, 1, 1, "SYNTHETIC-ROOT", "SYNTHETIC-SNAPSHOT-ROOT",
             "snapshot/attempt", '{"source":"SYNTHETIC"}', "SYNTHETIC-INPUT", "sealed", "SYNTHETIC-MARKER", _TIME,
             _TIME, _TIME),
        )
        connection.execute(
            "INSERT INTO archive_publish_intents(intent_id,attempt_id,task_id,deployment_instance_id,case_id,source_id,"
            "source_revision,draft_revision,report_fingerprint,source_key,input_fingerprint,archive_fingerprint,manifest_id,"
            "relative_final_dir,public_manifest_json,publication_id,publication_relative_dir,publication_digest,"
            "publication_file_set_json,publication_status,fence_id,phase,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (_INTENT, _ATTEMPT, _TASK, _DEPLOYMENT, _CASE, _SOURCE, 1, 1, "SYNTHETIC-REPORT", "SYNTHETIC-SOURCE-KEY",
             "SYNTHETIC-INPUT", "SYNTHETIC-ARCHIVE", "SYNTHETIC-MANIFEST", "formal", '{"manifest":"SYNTHETIC"}',
             _PUBLICATION, "formal", _DIGEST, json.dumps(_FILE_SET, separators=(",", ":")), "verified", _FENCE,
             "verified", _TIME, _TIME),
        )
        connection.execute(
            "INSERT INTO archive_assets VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (_WORK_ASSET, 1, _CASE, _TASK, _PLAN, "staging", "temporary", "staging/SYNTHETIC.work",
             '{"fingerprint":"SYNTHETIC-ASSET-FP"}', _TIME, _TIME, 1),
        )
        connection.execute(
            "INSERT INTO archive_assets VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (_ASSET, 1, _CASE, _TASK, _PLAN, "formal_rar", "published", "formal/SYNTHETIC.rar",
             '{"digest":"' + _DIGEST + '"}', _TIME, _TIME, 1),
        )


def _assert_graph(database: WorkbenchDatabase) -> None:
    with database.connect() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 11
        assert connection.execute("SELECT source_id FROM case_shells WHERE case_id=?", (_CASE,)).fetchone()[0] == _SOURCE
        assert connection.execute("SELECT source_id FROM archive_attempts WHERE attempt_id=?", (_ATTEMPT,)).fetchone()[0] == _SOURCE
        assert connection.execute("SELECT source_id FROM archive_input_snapshots WHERE snapshot_id=?", (_SNAPSHOT,)).fetchone()[0] == _SOURCE
        assert connection.execute("SELECT source_id FROM archive_context_bindings WHERE context_hash=?", (_CONTEXT,)).fetchone()[0] == _SOURCE
        assert connection.execute("SELECT report_json FROM case_drafts WHERE case_id=?", (_CASE,)).fetchone()[0] == '{"synthetic":true}'
        assert connection.execute("SELECT publication_id, publication_digest, publication_status, phase, publication_verified_at FROM archive_publish_intents WHERE intent_id=?", (_INTENT,)).fetchone()[0:4] == (_PUBLICATION, _DIGEST, "verified", "verified")
        assert connection.execute("SELECT publication_verified_at FROM archive_publish_intents WHERE intent_id=?", (_INTENT,)).fetchone()[0] is None
        assert connection.execute("SELECT COUNT(*) FROM archive_assets WHERE asset_id IN (?,?)", (_WORK_ASSET, _ASSET)).fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM asset_references WHERE asset_id=?", (_REFERENCE,)).fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM case_cleanup_runs").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM formal_word_artifacts").fetchone()[0] == 0
        assert connection.execute("SELECT mode FROM case_retention_policies").fetchone()[0] == "disabled"
        assert connection.execute("PRAGMA foreign_key_check").fetchone() is None
        snapshot_source = {row[1]: row for row in connection.execute("PRAGMA table_info(archive_input_snapshots)")}
        assert snapshot_source["source_id"][3] == 1
        phase_sql = connection.execute("SELECT sql FROM sqlite_master WHERE name='case_cleanup_runs'").fetchone()[0]
        assert "partial_failure" in phase_sql
        assert "cleanup_run_active_case" in {row[1] for row in connection.execute("PRAGMA index_list(case_cleanup_runs)")}


def test_populated_v10_graph_migrates_and_reopens_idempotently(tmp_path: Path) -> None:
    path = tmp_path / "SYNTHETIC-v10-graph.sqlite3"
    _build_v10_graph(path)
    database = WorkbenchDatabase(path, _DEPLOYMENT)
    _assert_graph(database)
    _assert_graph(WorkbenchDatabase(path, _DEPLOYMENT))


def test_populated_v10_graph_migration_rolls_back_as_a_unit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "SYNTHETIC-v10-rollback.sqlite3"
    _build_v10_graph(path)

    def fail_validation(_connection: sqlite3.Connection) -> None:
        raise sqlite3.DatabaseError("SYNTHETIC-MIGRATION-ROLLBACK")

    monkeypatch.setattr(database_module, "validate_schema", fail_validation)
    with pytest.raises(WorkbenchPersistenceError):
        WorkbenchDatabase(path, _DEPLOYMENT)

    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 10
        assert connection.execute("SELECT source_id FROM archive_attempts WHERE attempt_id=?", (_ATTEMPT,)).fetchone()[0] == _SOURCE
        assert connection.execute("SELECT publication_id FROM archive_publish_intents WHERE intent_id=?", (_INTENT,)).fetchone()[0] == _PUBLICATION
        for table in ("case_retention_policies", "case_retention_records", "case_cleanup_runs", "formal_word_artifacts"):
            assert connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone() is None
        assert connection.execute("SELECT name FROM sqlite_master WHERE name LIKE '%_v10'").fetchone() is None
        assert connection.execute("PRAGMA foreign_key_check").fetchone() is None

    monkeypatch.undo()
    database = WorkbenchDatabase(path, _DEPLOYMENT)
    _assert_graph(database)


def test_v11_statement_failure_rolls_back_without_half_built_schema(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "SYNTHETIC-v11-statement-failure.sqlite3"
    _build_v10_graph(path)
    broken_migrations = tuple(
        (version, statements + ("CREATE TABLE case_shells (synthetic_failure TEXT)",))
        if version == 11 else (version, statements)
        for version, statements in MIGRATIONS
    )
    monkeypatch.setattr(database_module, "MIGRATIONS", broken_migrations)
    with pytest.raises(WorkbenchPersistenceError, match="SQLITE_CORRUPTED"):
        WorkbenchDatabase(path, _DEPLOYMENT)

    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 10
        assert connection.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 10
        assert connection.execute(
            "SELECT source_id FROM archive_input_snapshots WHERE snapshot_id=?", (_SNAPSHOT,)
        ).fetchone()[0] == _SOURCE
        assert connection.execute(
            "SELECT publication_id FROM archive_publish_intents WHERE intent_id=?", (_INTENT,)
        ).fetchone()[0] == _PUBLICATION
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE name IN (?,?)", ("case_retention_policies", "formal_word_artifacts")
        ).fetchone() is None
        assert connection.execute("SELECT name FROM sqlite_master WHERE name LIKE '%_v10'").fetchone() is None
        assert connection.execute("PRAGMA foreign_key_check").fetchone() is None

    monkeypatch.undo()
    _assert_graph(WorkbenchDatabase(path, _DEPLOYMENT))
