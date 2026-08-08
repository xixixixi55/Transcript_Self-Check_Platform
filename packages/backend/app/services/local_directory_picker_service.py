"""Layer 21: trusted Windows native folder selection for local deployments."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Callable

from ..repository.local_directory_history_repository import (
    DirectoryHistoryKind,
    LocalDirectoryHistoryRepository,
)
from ..repository.workbench_errors import WorkbenchPersistenceError

logger = logging.getLogger(__name__)

PowerShellRunner = Callable[..., Any]

def _folder_picker_script(description: str, initial_directory: str | None = None) -> str:
    """Build the native dialog script with direct HWND Z-order enforcement."""
    safe_description = description.replace("'", "''")
    safe_initial = (initial_directory or "").replace("'", "''")
    return f"""
Add-Type -AssemblyName System.Windows.Forms;
Add-Type -TypeDefinition @'
using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading;
public static class PickerWindow {{
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
    public static readonly IntPtr HWND_TOPMOST = new IntPtr(-1);
    public const uint SWP_NOSIZE = 0x0001;
    public const uint SWP_NOMOVE = 0x0002;
    public const uint SWP_SHOWWINDOW = 0x0040;
    public static volatile bool WasRaised;
    public static volatile bool ForegroundRequested;
    private static volatile bool stopRequested;
    private static IntPtr ownerHandle;
    private static int processId;
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc callback, IntPtr lParam);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr insertAfter, int x, int y, int cx, int cy, uint flags);
    public static void StartPromotion(IntPtr owner) {{
        ownerHandle = owner;
        processId = Process.GetCurrentProcess().Id;
        WasRaised = false;
        ForegroundRequested = false;
        stopRequested = false;
        Thread worker = new Thread(PromoteDialog);
        worker.IsBackground = true;
        worker.Start();
    }}
    public static void StopPromotion() {{ stopRequested = true; }}
    private static void PromoteDialog() {{
        while (!stopRequested) {{
            IntPtr candidate = IntPtr.Zero;
            EnumWindows(delegate(IntPtr hWnd, IntPtr lParam) {{
                uint windowProcessId;
                GetWindowThreadProcessId(hWnd, out windowProcessId);
                if (windowProcessId == processId && hWnd != ownerHandle && IsWindowVisible(hWnd)) {{
                    candidate = hWnd;
                    return false;
                }}
                return true;
            }}, IntPtr.Zero);
            if (candidate != IntPtr.Zero) {{
                uint flags = SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW;
                if (SetWindowPos(candidate, HWND_TOPMOST, 0, 0, 0, 0, flags)) {{
                    WasRaised = true;
                    ForegroundRequested = SetForegroundWindow(candidate);
                    return;
                }}
            }}
            Thread.Sleep(50);
        }}
    }}
}}
'@;
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog;
$dialog.Description = '{safe_description}';
$dialog.RootFolder = [System.Environment+SpecialFolder]::MyComputer;
$dialog.ShowNewFolderButton = $false;
if ('{safe_initial}') {{ $dialog.SelectedPath = '{safe_initial}'; }}
$owner = New-Object System.Windows.Forms.Form;
$owner.TopMost = $true;
$owner.ShowInTaskbar = $false;
$owner.Opacity = 0;
$owner.Show();
$ownerHandle = $owner.Handle;
[PickerWindow]::StartPromotion($ownerHandle);
try {{
    $dialogResult = $dialog.ShowDialog($owner);
    if ($dialogResult -eq [System.Windows.Forms.DialogResult]::OK) {{
        if (-not [PickerWindow]::WasRaised) {{
            [Console]::Error.Write('PICKER_TOPMOST_NOT_CONFIRMED');
        }}
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8;
        [Console]::Write($dialog.SelectedPath);
    }}
}} finally {{
    [PickerWindow]::StopPromotion();
    $dialog.Dispose();
    $owner.Close();
    $owner.Dispose();
}}
"""
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
        history: LocalDirectoryHistoryRepository | None = None,
    ) -> None:
        self.runner = runner
        self.platform_name = platform_name or os.name
        self.powershell_path = powershell_path
        self.timeout_seconds = timeout_seconds
        self.history = history

    def select(
        self,
        description: str = "选择报告目录",
        *,
        history_kind: DirectoryHistoryKind | None = None,
    ) -> str | None:
        if self.platform_name != "nt":
            logger.warning("directory picker: unavailable on platform %s", self.platform_name)
            raise WorkbenchPersistenceError("DIRECTORY_PICKER_UNAVAILABLE")
        logger.info(
            "directory picker: launching native folder dialog (timeout=%ss)",
            self.timeout_seconds,
        )
        initial_directory = (
            self.history.last_directory(history_kind)
            if history_kind is not None and self.history is not None
            else None
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
                    _folder_picker_script(description, initial_directory),
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
        if "PICKER_TOPMOST_NOT_CONFIRMED" in (result.stderr or ""):
            logger.warning("directory picker: native topmost state was not confirmed")
        if history_kind is not None and self.history is not None:
            self.history.remember_directory(history_kind, candidate)
        logger.info("directory picker: directory selected")
        return str(candidate)

    def _resolve_powershell_path(self) -> str:
        if self.powershell_path:
            return self.powershell_path
        system_root = os.environ.get("SystemRoot", r"C:\Windows")
        candidate = Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        return str(candidate) if candidate.exists() else "powershell.exe"
