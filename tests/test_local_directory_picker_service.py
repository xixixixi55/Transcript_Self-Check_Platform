"""本地 Windows 原生文件夹选择器桥接层的单元测试。"""

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
from app.services.local_directory_picker_service import (  # noqa: E402
    LocalDirectoryPickerService,
    _folder_picker_script,
)


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
    assert "$ownerTypeDefinition = @'" in command[-1]
    assert "-ReferencedAssemblies @('System.dll', 'System.Windows.Forms.dll')" in command[-1]
    assert "ShowDialog($owner)" in command[-1]
    assert "WindowHandleOwner : IWin32Window" in command[-1]
    assert "CaptureForegroundOwner()" in command[-1]
    assert "$owner = [PickerWindow]::CaptureForegroundOwner()" in command[-1]
    assert "$fallbackOwner.TopMost = $true" in command[-1]
    assert "EnumWindows" in command[-1]
    assert "promotionWorker = new Thread(PromoteDialog)" in command[-1]
    assert "GetWindow(hWnd, GW_OWNER) == ownerHandle" in command[-1]
    assert 'className.ToString() == "#32770"' in command[-1]
    assert "return ownedCandidate != IntPtr.Zero ? ownedCandidate : dialogCandidate" in command[-1]
    assert "SetWindowPos(candidate, HWND_TOPMOST" in command[-1]
    assert "SWP_NOACTIVATE" in command[-1]
    assert "if (!ForegroundConfirmed)" in command[-1]
    assert "ForegroundConfirmed = GetForegroundWindow() == candidate" in command[-1]
    assert "Thread.Sleep(PROMOTION_INTERVAL_MS)" in command[-1]
    assert "Thread.Sleep(50)" not in command[-1]
    assert "worker.Join(PROMOTION_JOIN_TIMEOUT_MS)" in command[-1]
    assert "PICKER_TOPMOST_NOT_CONFIRMED" in command[-1]
    assert "PICKER_FOREGROUND_OWNER_NOT_CAPTURED" in command[-1]
    assert "PICKER_FOREGROUND_NOT_CONFIRMED" in command[-1]
    assert "exit 21" not in command[-1]
    assert "-Command" in command
    assert options["timeout"] == 600
    assert options["check"] is False


def test_picker_promotion_loop_cannot_exit_after_first_success_and_reactivates_new_handle(tmp_path: Path):
    commands: list[list[str]] = []

    def runner(command: list[str], **_kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout=str(tmp_path), stderr="")

    LocalDirectoryPickerService(runner=runner, platform_name="nt").select()

    script = commands[0][-1]
    promotion_body = script.split("private static void PromoteDialog() {", 1)[1].split("\n    }\n}\n'@;", 1)[0]
    assert "while (!stopRequested)" in promotion_body
    assert "return;" not in promotion_body
    assert promotion_body.index("candidate != lastCandidate") < promotion_body.index(
        "ForegroundConfirmed = false",
    )
    assert promotion_body.index("SetWindowPos(candidate, HWND_TOPMOST") < promotion_body.index(
        "Thread.Sleep(PROMOTION_INTERVAL_MS)",
    )
    assert "SWP_NOACTIVATE" in promotion_body


@pytest.mark.skipif(os.name != "nt", reason="PowerShell WinForms compilation requires Windows")
def test_generated_picker_native_owner_type_compiles() -> None:
    type_definition = _folder_picker_script("SYNTHETIC").split("$dialog =", 1)[0]
    result = subprocess.run(
        [
            str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" /
                "WindowsPowerShell" / "v1.0" / "powershell.exe"),
            "-NoLogo", "-NoProfile", "-STA", "-Command",
            type_definition + "[Console]::Write('SYNTHETIC-COMPILED');",
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=30, check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "SYNTHETIC-COMPILED"


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


def test_export_picker_validation_runs_before_history_update(tmp_path: Path):
    previous = tmp_path / "SYNTHETIC-PREVIOUS"
    rejected = tmp_path / "SYNTHETIC-REJECTED"
    previous.mkdir()
    rejected.mkdir()
    history = LocalDirectoryHistoryRepository(tmp_path / "history.json")
    history.remember_directory("export", previous)
    picker = LocalDirectoryPickerService(
        runner=lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0, stdout=str(rejected), stderr="",
        ),
        platform_name="nt",
        history=history,
    )

    def reject(_path: Path) -> None:
        raise WorkbenchPersistenceError("EXPORT_DIRECTORY_UNSAFE")

    with pytest.raises(WorkbenchPersistenceError) as failure:
        picker.select(history_kind="export", selection_validator=reject)

    assert failure.value.code == "EXPORT_DIRECTORY_UNSAFE"
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


def test_picker_keeps_valid_selection_when_foreground_owner_or_activation_is_unconfirmed(
    tmp_path: Path, caplog: pytest.LogCaptureFixture,
):
    picker = LocalDirectoryPickerService(
        runner=lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout=str(tmp_path),
            stderr="PICKER_FOREGROUND_OWNER_NOT_CAPTURED;PICKER_FOREGROUND_NOT_CONFIRMED;",
        ),
        platform_name="nt",
    )

    with caplog.at_level("WARNING"):
        assert picker.select() == str(tmp_path)
    assert "fallback owner used" in caplog.text
    assert "foreground activation was not confirmed" in caplog.text


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
