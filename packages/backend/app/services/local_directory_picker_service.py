"""第 21 层：本地部署的可信 Windows 原生文件夹选择。"""

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
SelectionValidator = Callable[[Path], Any]

def _folder_picker_script(description: str, initial_directory: str | None = None) -> str:
    """构建原生对话框脚本并直接实施 HWND Z 顺序。"""
    safe_description = description.replace("'", "''")
    safe_initial = (initial_directory or "").replace("'", "''")
    return f"""
Add-Type -AssemblyName System.Windows.Forms;
$ownerTypeDefinition = @'
using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;
public sealed class WindowHandleOwner : IWin32Window {{
    public WindowHandleOwner(IntPtr handle) {{ Handle = handle; }}
    public IntPtr Handle {{ get; private set; }}
}}
public static class PickerWindow {{
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
    public static readonly IntPtr HWND_TOPMOST = new IntPtr(-1);
    public const uint SWP_NOSIZE = 0x0001;
    public const uint SWP_NOMOVE = 0x0002;
    public const uint SWP_NOACTIVATE = 0x0010;
    public const uint SWP_SHOWWINDOW = 0x0040;
    public const uint GW_OWNER = 4;
    public const int PROMOTION_INTERVAL_MS = 100;
    public const int PROMOTION_JOIN_TIMEOUT_MS = 1000;
    public static volatile bool WasRaised;
    public static volatile bool ForegroundConfirmed;
    private static volatile bool stopRequested;
    private static IntPtr ownerHandle;
    private static int processId;
    private static Thread promotionWorker;
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc callback, IntPtr lParam);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern IntPtr GetWindow(IntPtr hWnd, uint command);
    [DllImport("user32.dll", CharSet = CharSet.Auto)] public static extern int GetClassName(IntPtr hWnd, StringBuilder className, int maxCount);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr insertAfter, int x, int y, int cx, int cy, uint flags);
    public static WindowHandleOwner CaptureForegroundOwner() {{
        IntPtr handle = GetForegroundWindow();
        if (handle == IntPtr.Zero) return null;
        uint foregroundProcessId;
        GetWindowThreadProcessId(handle, out foregroundProcessId);
        return foregroundProcessId == Process.GetCurrentProcess().Id
            ? null : new WindowHandleOwner(handle);
    }}
    public static void StartPromotion(IntPtr owner) {{
        ownerHandle = owner;
        processId = Process.GetCurrentProcess().Id;
        WasRaised = false;
        ForegroundConfirmed = false;
        stopRequested = false;
        promotionWorker = new Thread(PromoteDialog);
        promotionWorker.IsBackground = true;
        promotionWorker.Start();
    }}
    public static void StopPromotion() {{
        stopRequested = true;
        Thread worker = promotionWorker;
        if (worker != null && worker != Thread.CurrentThread) {{
            worker.Join(PROMOTION_JOIN_TIMEOUT_MS);
        }}
        promotionWorker = null;
    }}
    private static IntPtr FindDialog() {{
        IntPtr ownedCandidate = IntPtr.Zero;
        IntPtr dialogCandidate = IntPtr.Zero;
        EnumWindows(delegate(IntPtr hWnd, IntPtr lParam) {{
            uint windowProcessId;
            GetWindowThreadProcessId(hWnd, out windowProcessId);
            if (windowProcessId == processId && hWnd != ownerHandle && IsWindowVisible(hWnd)) {{
                if (GetWindow(hWnd, GW_OWNER) == ownerHandle) {{
                    ownedCandidate = hWnd;
                    return false;
                }}
                StringBuilder className = new StringBuilder(64);
                GetClassName(hWnd, className, className.Capacity);
                if (className.ToString() == "#32770") {{
                    dialogCandidate = hWnd;
                }}
            }}
            return true;
        }}, IntPtr.Zero);
        return ownedCandidate != IntPtr.Zero ? ownedCandidate : dialogCandidate;
    }}
    private static void PromoteDialog() {{
        IntPtr lastCandidate = IntPtr.Zero;
        while (!stopRequested) {{
            IntPtr candidate = FindDialog();
            if (candidate != IntPtr.Zero) {{
                if (candidate != lastCandidate) {{
                    lastCandidate = candidate;
                    ForegroundConfirmed = false;
                }}
                uint flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_SHOWWINDOW;
                if (SetWindowPos(candidate, HWND_TOPMOST, 0, 0, 0, 0, flags)) {{
                    WasRaised = true;
                    if (!ForegroundConfirmed) {{
                        SetForegroundWindow(candidate);
                        ForegroundConfirmed = GetForegroundWindow() == candidate;
                    }}
                }}
            }}
            Thread.Sleep(PROMOTION_INTERVAL_MS);
        }}
    }}
}}
'@;
Add-Type -TypeDefinition $ownerTypeDefinition `
    -ReferencedAssemblies @('System.dll', 'System.Windows.Forms.dll');
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog;
$dialog.Description = '{safe_description}';
$dialog.RootFolder = [System.Environment+SpecialFolder]::MyComputer;
$dialog.ShowNewFolderButton = $false;
if ('{safe_initial}') {{ $dialog.SelectedPath = '{safe_initial}'; }}
$owner = [PickerWindow]::CaptureForegroundOwner();
$fallbackOwner = $null;
if ($null -eq $owner) {{
    [Console]::Error.Write('PICKER_FOREGROUND_OWNER_NOT_CAPTURED;');
    $fallbackOwner = New-Object System.Windows.Forms.Form;
    $fallbackOwner.TopMost = $true;
    $fallbackOwner.ShowInTaskbar = $false;
    $fallbackOwner.Opacity = 0;
    $fallbackOwner.Show();
    $owner = $fallbackOwner;
}}
$ownerHandle = $owner.Handle;
[PickerWindow]::StartPromotion($ownerHandle);
try {{
    $dialogResult = $dialog.ShowDialog($owner);
    if ($dialogResult -eq [System.Windows.Forms.DialogResult]::OK) {{
        if (-not [PickerWindow]::WasRaised) {{
            [Console]::Error.Write('PICKER_TOPMOST_NOT_CONFIRMED;');
        }}
        if (-not [PickerWindow]::ForegroundConfirmed) {{
            [Console]::Error.Write('PICKER_FOREGROUND_NOT_CONFIRMED;');
        }}
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8;
        [Console]::Write($dialog.SelectedPath);
    }}
}} finally {{
    [PickerWindow]::StopPromotion();
    $dialog.Dispose();
    if ($null -ne $fallbackOwner) {{
        $fallbackOwner.Close();
        $fallbackOwner.Dispose();
    }}
}}
"""
_PICKER_TIMEOUT_SECONDS = 600


class LocalDirectoryPickerService:
    """打开原生选择器，不暴露或复制所选路径。"""

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
        selection_validator: SelectionValidator | None = None,
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
        if selection_validator is not None:
            selection_validator(candidate)
        if "PICKER_TOPMOST_NOT_CONFIRMED" in (result.stderr or ""):
            logger.warning("directory picker: native topmost state was not confirmed")
        if "PICKER_FOREGROUND_OWNER_NOT_CAPTURED" in (result.stderr or ""):
            logger.warning("directory picker: foreground owner was not captured; fallback owner used")
        if "PICKER_FOREGROUND_NOT_CONFIRMED" in (result.stderr or ""):
            logger.warning("directory picker: native foreground activation was not confirmed")
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
