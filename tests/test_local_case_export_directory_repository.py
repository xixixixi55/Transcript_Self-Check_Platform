from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.local_case_export_directory_repository import (  # noqa: E402
    LocalCaseExportDirectoryRepository,
)
from app.repository.case.case_workbench_repository import CaseShellRepository  # noqa: E402
from app.repository.workbench_database import (  # noqa: E402
    WorkbenchDatabase,
    database_path_for_deployment,
)
from app.services.case.case_lifecycle_service import CaseLifecycleService  # noqa: E402


def test_latest_export_directory_is_persisted_and_isolated_by_case(tmp_path: Path) -> None:
    repository = LocalCaseExportDirectoryRepository(tmp_path / "case-exports.json")
    directories = {
        "SYNTHETIC-CASE-A1": tmp_path / "SYNTHETIC-A1",
        "SYNTHETIC-CASE-A2": tmp_path / "SYNTHETIC-A2",
        "SYNTHETIC-CASE-B1": tmp_path / "SYNTHETIC-B1",
    }
    for directory in directories.values():
        directory.mkdir()

    repository.remember(
        "SYNTHETIC-CASE-A", directories["SYNTHETIC-CASE-A1"],
        "2026-08-26T08:00:00Z",
    )
    repository.remember(
        "SYNTHETIC-CASE-B", directories["SYNTHETIC-CASE-B1"],
        "2026-08-26T09:00:00Z",
    )
    repository.remember(
        "SYNTHETIC-CASE-A", directories["SYNTHETIC-CASE-A2"],
        "2026-08-26T10:00:00Z",
    )

    recreated = LocalCaseExportDirectoryRepository(tmp_path / "case-exports.json")
    assert recreated.latest("SYNTHETIC-CASE-A") == {
        "case_id": "SYNTHETIC-CASE-A",
        "export_path": str(directories["SYNTHETIC-CASE-A2"].resolve()),
        "exported_at": "2026-08-26T10:00:00+00:00",
    }
    assert recreated.latest("SYNTHETIC-CASE-B")["export_path"] == str(
        directories["SYNTHETIC-CASE-B1"].resolve()
    )


def test_missing_directory_remains_bound_for_actionable_open_error(tmp_path: Path) -> None:
    repository = LocalCaseExportDirectoryRepository(tmp_path / "case-exports.json")
    directory = tmp_path / "SYNTHETIC-REMOVED-LATER"
    directory.mkdir()
    repository.remember(
        "SYNTHETIC-CASE-A", directory, "2026-08-26T10:00:00Z",
    )
    directory.rmdir()

    assert repository.latest("SYNTHETIC-CASE-A")["export_path"] == str(directory.resolve())


def test_workbench_list_restores_last_export_marker_after_restart(tmp_path: Path) -> None:
    database = WorkbenchDatabase(
        database_path_for_deployment(tmp_path, "SYNTHETIC-EXPORT-MARKER"),
        "SYNTHETIC-EXPORT-MARKER",
    )
    CaseShellRepository(database).create({
        "case_id": "SYNTHETIC-CASE-A",
        "case_name": "SYNTHETIC/TEST/A",
        "case_summary": "SYNTHETIC/TEST",
        "source_id": "SYNTHETIC-SOURCE-A",
        "parse_task_id": "SYNTHETIC-TASK-A",
    })
    export_dir = tmp_path / "SYNTHETIC-EXPORT-A"
    export_dir.mkdir()
    writer = CaseLifecycleService(database)
    writer.export_directories.remember(
        "SYNTHETIC-CASE-A", export_dir, "2026-08-26T10:00:00Z",
    )

    restarted = CaseLifecycleService(database)
    item = restarted.list(0, 6)["items"][0]
    assert item["last_unified_export_at"] == "2026-08-26T10:00:00+00:00"
