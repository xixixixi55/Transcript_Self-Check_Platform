"""Unit tests for the local Windows native folder picker bridge."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages", "backend"))

from app.repository.workbench_errors import WorkbenchPersistenceError  # noqa: E402
from app.repository.local_directory_history_repository import LocalDirectoryHistoryRepository  # noqa: E402
from app.services.local_directory_picker_service import LocalDirectoryPickerService  # noqa: E402


def test_picker_returns_selected_absolute_directory_and_uses_fixed_native_command(tmp_path: Path):
    calls: list[tuple[list[str], dict]] = []

    def runner(command: list[str], **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=str(tmp_path), stderr="")

    selected = LocalDirectoryPickerService(
        runner=runner, platform_name="nt", powershell_path="powershell.exe",
    ).select()

    assert selected == str(tmp_path)
    command, options = calls[0]
    assert command[:6] == ["powershell.exe", "-NoLogo", "-NoProfile", "-STA", "-WindowStyle", "Hidden"]
    assert "FolderBrowserDialog" in command[-1]
    assert "ShowDialog($owner)" in command[-1]
    assert "$owner.TopMost = $true" in command[-1]
    assert "EnumWindows" in command[-1]
    assert "Thread worker = new Thread(PromoteDialog)" in command[-1]
    assert "SetWindowPos(candidate, HWND_TOPMOST" in command[-1]
    assert "ForegroundRequested = SetForegroundWindow(candidate)" in command[-1]
    assert "PICKER_TOPMOST_NOT_CONFIRMED" in command[-1]
    assert "exit 21" not in command[-1]
    assert "-Command" in command
    assert options["timeout"] == 600
    assert options["check"] is False


def test_picker_cancel_returns_none_without_path_validation(tmp_path: Path):
    picker = LocalDirectoryPickerService(
        runner=lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="\r\n"),
        platform_name="nt",
    )

    assert picker.select() is None


def test_export_picker_uses_and_updates_persisted_directory(tmp_path: Path):
    previous = tmp_path / "SYNTHETIC-PREVIOUS"
    selected = tmp_path / "SYNTHETIC-SELECTED"
    previous.mkdir()
    selected.mkdir()
    history = LocalDirectoryHistoryRepository(tmp_path / "history.json")
    history.remember_directory("export", previous)
    calls: list[list[str]] = []

    def runner(command: list[str], **_kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout=str(selected), stderr="")

    picker = LocalDirectoryPickerService(
        runner=runner,
        platform_name="nt",
        powershell_path="powershell.exe",
        history=history,
    )

    assert picker.select(history_kind="export") == str(selected)
    assert f"$dialog.SelectedPath = '{previous}'" in calls[0][-1]
    assert history.last_directory("export") == str(selected)


def test_export_picker_cancel_preserves_persisted_directory(tmp_path: Path):
    previous = tmp_path / "SYNTHETIC-PREVIOUS"
    previous.mkdir()
    history = LocalDirectoryHistoryRepository(tmp_path / "history.json")
    history.remember_directory("export", previous)
    picker = LocalDirectoryPickerService(
        runner=lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
        platform_name="nt",
        history=history,
    )

    assert picker.select(history_kind="export") is None
    assert history.last_directory("export") == str(previous)


def test_picker_escapes_quotes_in_description_and_initial_directory(tmp_path: Path):
    previous = tmp_path / "SYNTHETIC 中文 ' EXPORT"
    previous.mkdir()
    history = LocalDirectoryHistoryRepository(tmp_path / "history.json")
    history.remember_directory("export", previous)
    commands: list[list[str]] = []

    def runner(command: list[str], **_kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    picker = LocalDirectoryPickerService(
        runner=runner, platform_name="nt", history=history,
    )
    picker.select(description="选择 ' 合成目录", history_kind="export")

    script = commands[0][-1]
    assert "$dialog.Description = '选择 '' 合成目录'" in script
    escaped_previous = str(previous).replace("'", "''")
    assert f"$dialog.SelectedPath = '{escaped_previous}'" in script


def test_picker_keeps_valid_selection_when_native_topmost_confirmation_is_missing(tmp_path: Path):
    history = LocalDirectoryHistoryRepository(tmp_path / "history.json")
    picker = LocalDirectoryPickerService(
        runner=lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=str(tmp_path),
            stderr="PICKER_TOPMOST_NOT_CONFIRMED",
        ),
        platform_name="nt",
        history=history,
    )

    assert picker.select(history_kind="export") == str(tmp_path)
    assert history.last_directory("export") == str(tmp_path)


def test_report_and_export_picker_histories_are_independent(tmp_path: Path):
    report = tmp_path / "SYNTHETIC-REPORT"
    export = tmp_path / "SYNTHETIC-EXPORT"
    report.mkdir()
    export.mkdir()
    history = LocalDirectoryHistoryRepository(tmp_path / "history.json")
    history.remember_directory("report", report)
    history.remember_directory("export", export)
    commands: list[list[str]] = []

    def runner(command: list[str], **_kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    picker = LocalDirectoryPickerService(runner=runner, platform_name="nt", history=history)
    picker.select(history_kind="report")
    picker.select(history_kind="export")

    assert f"$dialog.SelectedPath = '{report}'" in commands[0][-1]
    assert f"$dialog.SelectedPath = '{export}'" in commands[1][-1]


@pytest.mark.parametrize(
    ("platform_name", "expected_code"),
    [("posix", "DIRECTORY_PICKER_UNAVAILABLE")],
)
def test_picker_rejects_non_windows_runtime(platform_name: str, expected_code: str):
    with pytest.raises(WorkbenchPersistenceError) as failure:
        LocalDirectoryPickerService(platform_name=platform_name).select()
    assert failure.value.code == expected_code


def test_picker_rejects_invalid_selection(tmp_path: Path):
    missing = tmp_path / "SYNTHETIC-MISSING"
    picker = LocalDirectoryPickerService(
        runner=lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout=str(missing)),
        platform_name="nt",
    )

    with pytest.raises(WorkbenchPersistenceError) as failure:
        picker.select()
    assert failure.value.code == "DIRECTORY_PICKER_FAILED"


def test_picker_maps_process_timeout_to_stable_unavailable_error():
    def runner(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("powershell.exe", 600)

    with pytest.raises(WorkbenchPersistenceError) as failure:
        LocalDirectoryPickerService(runner=runner, platform_name="nt").select()
    assert failure.value.code == "DIRECTORY_PICKER_UNAVAILABLE"
