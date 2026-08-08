"""Synthetic tests for persisted native-picker directory history."""

from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.local_directory_history_repository import (  # noqa: E402
    LocalDirectoryHistoryRepository,
)


def test_report_and_export_directories_survive_repository_recreation(tmp_path: Path):
    selected = tmp_path / "SYNTHETIC-EXPORT"
    report = tmp_path / "SYNTHETIC-REPORT"
    selected.mkdir()
    report.mkdir()
    history_path = tmp_path / "history.json"

    repository = LocalDirectoryHistoryRepository(history_path)
    repository.remember_directory("report", report)
    repository.remember_directory("export", selected)

    recreated = LocalDirectoryHistoryRepository(history_path)
    assert recreated.last_directory("report") == str(report)
    assert recreated.last_directory("export") == str(selected)
    payload = json.loads(history_path.read_text(encoding="utf-8"))
    assert payload == {
        "schema_version": 1,
        "directories": {"report": str(report), "export": str(selected)},
    }


def test_missing_directory_and_corrupt_history_safely_fall_back(tmp_path: Path):
    history_path = tmp_path / "history.json"
    missing = tmp_path / "SYNTHETIC-MISSING"
    history_path.write_text(
        json.dumps({"schema_version": 1, "directories": {"export": str(missing)}}),
        encoding="utf-8",
    )
    repository = LocalDirectoryHistoryRepository(history_path)
    assert repository.last_directory("export") is None

    history_path.write_text("{broken", encoding="utf-8")
    assert repository.last_directory("export") is None


def test_invalid_selection_does_not_replace_valid_history(tmp_path: Path):
    selected = tmp_path / "SYNTHETIC-EXPORT"
    selected.mkdir()
    repository = LocalDirectoryHistoryRepository(tmp_path / "history.json")
    repository.remember_directory("export", selected)

    repository.remember_directory("export", tmp_path / "SYNTHETIC-MISSING")

    assert repository.last_directory("export") == str(selected)


def test_legacy_export_directory_is_preserved_on_first_new_write(tmp_path: Path):
    export = tmp_path / "SYNTHETIC-LEGACY-EXPORT"
    report = tmp_path / "SYNTHETIC-REPORT"
    export.mkdir()
    report.mkdir()
    history_path = tmp_path / "history.json"
    history_path.write_text(
        json.dumps({"schema_version": 1, "export_directory": str(export)}),
        encoding="utf-8",
    )
    repository = LocalDirectoryHistoryRepository(history_path)

    repository.remember_directory("report", report)

    assert repository.last_directory("export") == str(export)
    assert repository.last_directory("report") == str(report)


def test_concurrent_repository_instances_leave_complete_history(tmp_path: Path):
    export_directories = [tmp_path / f"SYNTHETIC-EXPORT-{index}" for index in range(4)]
    report_directories = [tmp_path / f"SYNTHETIC-REPORT-{index}" for index in range(4)]
    for directory in [*export_directories, *report_directories]:
        directory.mkdir()
    history_path = tmp_path / "history.json"
    writes = [
        *(('export', directory) for directory in export_directories),
        *(('report', directory) for directory in report_directories),
    ]

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(
            lambda item: LocalDirectoryHistoryRepository(history_path).remember_directory(*item),
            writes,
        ))

    payload = json.loads(history_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert Path(payload["directories"]["export"]) in export_directories
    assert Path(payload["directories"]["report"]) in report_directories
    repository = LocalDirectoryHistoryRepository(history_path)
    assert repository.last_directory("export") in {str(path) for path in export_directories}
    assert repository.last_directory("report") in {str(path) for path in report_directories}
