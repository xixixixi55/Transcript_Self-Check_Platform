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
    assert "-Command" in command
    assert options["timeout"] == 600
    assert options["check"] is False


def test_picker_cancel_returns_none_without_path_validation(tmp_path: Path):
    picker = LocalDirectoryPickerService(
        runner=lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="\r\n"),
        platform_name="nt",
    )

    assert picker.select() is None


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
