"""Layer 21: trusted Windows native folder selection for local deployments."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Callable

from ..repository.workbench_errors import WorkbenchPersistenceError

PowerShellRunner = Callable[..., Any]

_FOLDER_PICKER_SCRIPT = (
    "Add-Type -AssemblyName System.Windows.Forms;"
    "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog;"
    "$dialog.Description = '选择报告目录';"
    "$dialog.RootFolder = [System.Environment+SpecialFolder]::MyComputer;"
    "$dialog.ShowNewFolderButton = $false;"
    "if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {"
    "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;"
    "[Console]::Write($dialog.SelectedPath)"
    "}"
)
_PICKER_TIMEOUT_SECONDS = 600


class LocalDirectoryPickerService:
    """Open a native picker without exposing or copying the selected path."""

    def __init__(
        self,
        runner: PowerShellRunner = subprocess.run,
        *,
        platform_name: str | None = None,
        powershell_path: str | None = None,
        timeout_seconds: float = _PICKER_TIMEOUT_SECONDS,
    ) -> None:
        self.runner = runner
        self.platform_name = platform_name or os.name
        self.powershell_path = powershell_path
        self.timeout_seconds = timeout_seconds

    def select(self) -> str | None:
        if self.platform_name != "nt":
            raise WorkbenchPersistenceError("DIRECTORY_PICKER_UNAVAILABLE")
        try:
            result = self.runner(
                [
                    self._resolve_powershell_path(),
                    "-NoLogo",
                    "-NoProfile",
                    "-STA",
                    "-WindowStyle",
                    "Hidden",
                    "-Command",
                    _FOLDER_PICKER_SCRIPT,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise WorkbenchPersistenceError("DIRECTORY_PICKER_UNAVAILABLE") from error
        if result.returncode != 0:
            raise WorkbenchPersistenceError("DIRECTORY_PICKER_FAILED")
        selected = (result.stdout or "").strip().lstrip("\ufeff")
        if not selected:
            return None
        candidate = Path(selected)
        if not candidate.is_absolute() or not candidate.is_dir():
            raise WorkbenchPersistenceError("DIRECTORY_PICKER_FAILED")
        return str(candidate)

    def _resolve_powershell_path(self) -> str:
        if self.powershell_path:
            return self.powershell_path
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        candidate = Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        return str(candidate) if candidate.exists() else "powershell.exe"
