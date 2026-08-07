"""Layer 21: trusted Windows native folder selection for local deployments."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Callable

from ..repository.workbench_errors import WorkbenchPersistenceError

logger = logging.getLogger(__name__)

PowerShellRunner = Callable[..., Any]

def _folder_picker_script(description: str) -> str:
    """PowerShell folder dialog script; description is doubled up to survive single quotes."""
    safe = description.replace("'", "''")
    return (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog;"
        f"$dialog.Description = '{safe}';"
        "$dialog.RootFolder = [System.Environment+SpecialFolder]::MyComputer;"
        "$dialog.ShowNewFolderButton = $false;"
        # 隐藏的 TopMost 所有者窗体：从后台服务弹出的对话框默认可能落在浏览器窗口后面而不可见。
        # TopMost 让对话框的 Z 序始终高于浏览器等非 TopMost 窗口，保证可见且可点击。
        "$owner = New-Object System.Windows.Forms.Form;"
        "$owner.TopMost = $true;"
        "$owner.ShowInTaskbar = $false;"
        "$owner.Opacity = 0;"
        "$owner.Show();"
        "$owner.Activate();"
        "if ($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) {"
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8;"
        "[Console]::Write($dialog.SelectedPath)"
        "}"
        "$owner.Close();"
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

    def select(self, description: str = "选择报告目录") -> str | None:
        if self.platform_name != "nt":
            logger.warning("directory picker: unavailable on platform %s", self.platform_name)
            raise WorkbenchPersistenceError("DIRECTORY_PICKER_UNAVAILABLE")
        logger.info(
            "directory picker: launching native folder dialog (timeout=%ss)",
            self.timeout_seconds,
        )
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
                    _folder_picker_script(description),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired as error:
            logger.error(
                "directory picker: PowerShell dialog timed out after %ss (stderr=%r)",
                self.timeout_seconds, (error.stderr or "")[:500],
            )
            raise WorkbenchPersistenceError("DIRECTORY_PICKER_UNAVAILABLE") from error
        except OSError as error:
            logger.error("directory picker: PowerShell launch failed: %s", error)
            raise WorkbenchPersistenceError("DIRECTORY_PICKER_UNAVAILABLE") from error
        logger.info("directory picker: PowerShell returned (returncode=%s)", result.returncode)
        if result.returncode != 0:
            logger.error(
                "directory picker: PowerShell picker failed (returncode=%s, stderr=%r)",
                result.returncode, (result.stderr or "")[:500],
            )
            raise WorkbenchPersistenceError("DIRECTORY_PICKER_FAILED")
        selected = (result.stdout or "").strip().lstrip("\ufeff")
        if not selected:
            logger.info("directory picker: dialog closed without a selection")
            return None
        candidate = Path(selected)
        if not candidate.is_absolute() or not candidate.is_dir():
            logger.error("directory picker: selected path rejected by safety checks")
            raise WorkbenchPersistenceError("DIRECTORY_PICKER_FAILED")
        logger.info("directory picker: directory selected")
        return str(candidate)

    def _resolve_powershell_path(self) -> str:
        if self.powershell_path:
            return self.powershell_path
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        candidate = Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        return str(candidate) if candidate.exists() else "powershell.exe"
