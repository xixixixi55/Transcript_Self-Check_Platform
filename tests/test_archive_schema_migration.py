"""T013 v6 之前 TaskRecord 数据行的兼容性覆盖测试。"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository import TaskRecordRepository, WorkbenchDatabase  # noqa: E402
from app.repository.workbench.workbench_schema import MIGRATIONS  # noqa: E402


def test_v5_archive_task_migrates_with_safe_restart_defaults(tmp_path: Path) -> None:
    path = tmp_path / "SYNTHETIC-v5.sqlite3"
    connection = sqlite3.connect(path)
    for version, statements in MIGRATIONS:
        if version > 5:
            break
        for statement in statements:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO schema_migrations(version,applied_at) VALUES (?,?)",
            (version, "2026-07-30T00:00:00+00:00"),
        )
    connection.execute("PRAGMA user_version = 5")
    connection.execute(
        "INSERT INTO case_shells VALUES "
        "('SYNTHETIC-LEGACY-CASE',1,NULL,'SYNTHETIC/TEST','SYNTHETIC/TEST',"
        "'SYNTHETIC-SOURCE','SYNTHETIC-PARSE','archiving',1,0,"
        "'2026-07-30T00:00:00+00:00','2026-07-30T00:00:00+00:00')"
    )
    connection.execute(
        "INSERT INTO task_records VALUES "
        "('SYNTHETIC-LEGACY-TASK',1,'SYNTHETIC-LEGACY-CASE','archive','running',"
        "'winrar',30,'{}',1,0,NULL,NULL,NULL,0,"
        "'2026-07-30T00:00:00+00:00','2026-07-30T00:00:00+00:00',NULL,0)"
    )
    connection.commit()
    connection.close()

    database = WorkbenchDatabase(path, "SYNTHETIC-LEGACY")
    task = TaskRecordRepository(database).get("SYNTHETIC-LEGACY-TASK")
    assert database.schema_version() == 11
    assert task["updated_at"] == "2026-07-30T00:00:00+00:00"
    assert task["worker_state"] == "waiting_reclaim"
    assert task["output_bytes"] is None
