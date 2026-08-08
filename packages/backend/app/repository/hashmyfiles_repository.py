"""Run the real HashMyFiles.exe window and capture its three-column result."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

_HASH_IMAGE_FILENAME = "hash-verification.png"
_LEGACY_HASH_HTML_FILENAME = "hash-verification.html"
# Probed against HashMyFiles v2.51 on Windows (2026-08-06); shown in the
# report's software_tools runtime entry for newly parsed cases.
HASHMYFILES_DISPLAY_VERSION = "2.51"
_HASH_TYPES_ARGS = [
    "/MD5", "1", "/SHA1", "0", "/CRC32", "0",
    "/SHA256", "0", "/SHA512", "0", "/SHA384", "0",
]
# Bundled default shipped with the repository: packages/backend -> root/hashmyfiles.
_DEFAULT_TOOL_PATH = Path(__file__).resolve().parents[4] / "hashmyfiles" / "HashMyFiles.exe"


class HashMyFilesError(RuntimeError):
    """Stable, path-free diagnostic for HashMyFiles failures."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def resolve_hashmyfiles() -> Path | None:
    """Resolve HashMyFiles.exe; env override first, then the bundled default."""
    override = os.environ.get("BIJI_HASHMYFILES_PATH")
    if override:
        candidate = Path(override)
        if candidate.is_file():
            return candidate
    if _DEFAULT_TOOL_PATH.is_file():
        return _DEFAULT_TOOL_PATH
    return None


def run_hashmyfiles(
    executable: Path,
    rar_paths: list[Path],
    output_dir: Path,
    timeout_seconds: int = 120,
) -> str:
    """Produce the verification PNG file name inside ``output_dir``.

    Only MD5 is enabled. The real HashMyFiles window is captured after its
    native list view is reduced to Filename, MD5, and File Size.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    image_path = output_dir / _HASH_IMAGE_FILENAME
    legacy_html_path = output_dir / _LEGACY_HASH_HTML_FILENAME
    # Keep the previous published artifact intact until the replacement has
    # been fully generated and validated on the same filesystem.
    with tempfile.TemporaryDirectory(
        prefix=".biji-hashmyfiles-", dir=output_dir,
    ) as temp_dir:
        candidate_image_path = Path(temp_dir) / _HASH_IMAGE_FILENAME
        _capture_hashmyfiles_window(
            executable, rar_paths, candidate_image_path, timeout_seconds,
        )
        _validate_png(candidate_image_path)
        try:
            os.replace(candidate_image_path, image_path)
        except OSError as error:
            raise HashMyFilesError(
                "HASHMYFILES_SCREENSHOT_FAILED", "HashMyFiles 校验截图发布失败。",
            ) from error
    legacy_html_path.unlink(missing_ok=True)
    return _HASH_IMAGE_FILENAME


def _validate_png(image_path: Path) -> None:
    try:
        with image_path.open("rb") as image_file:
            signature = image_file.read(8)
            has_payload = bool(image_file.read(1))
    except OSError as error:
        raise HashMyFilesError(
            "HASHMYFILES_SCREENSHOT_MISSING", "HashMyFiles 校验截图未生成。",
        ) from error
    if signature != b"\x89PNG\r\n\x1a\n" or not has_payload:
        raise HashMyFilesError(
            "HASHMYFILES_SCREENSHOT_INVALID", "HashMyFiles 校验截图无效。",
        )


def _capture_hashmyfiles_window(
    executable: Path,
    rar_paths: list[Path],
    output_path: Path,
    timeout_seconds: int,
) -> None:
    try:
        with tempfile.TemporaryDirectory(prefix="biji-hash-capture-") as temp_dir:
            payload_path = Path(temp_dir) / "capture.json"
            script_path = Path(temp_dir) / "render.ps1"
            result_path = Path(temp_dir) / "result.json"
            payload_path.write_text(json.dumps({
                "executable": str(executable),
                "files": [str(path) for path in rar_paths],
                "expected_count": len(rar_paths),
                "timeout_seconds": timeout_seconds,
                "hash_arguments": _HASH_TYPES_ARGS,
            }, ensure_ascii=False), encoding="utf-8")
            script_path.write_text(_CAPTURE_SCRIPT, encoding="utf-8-sig")
            result = subprocess.run(
                [
                    "powershell.exe", "-NoProfile", "-NonInteractive",
                    "-ExecutionPolicy", "Bypass", "-File", str(script_path),
                    str(payload_path), str(output_path), str(result_path),
                ],
                capture_output=True, timeout=timeout_seconds + 15, check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode != 0:
                raise HashMyFilesError(
                    "HASHMYFILES_SCREENSHOT_FAILED", "HashMyFiles 校验截图生成失败。",
                )
            try:
                capture_result = json.loads(result_path.read_text(encoding="utf-8-sig"))
            except (OSError, UnicodeError, json.JSONDecodeError) as error:
                raise HashMyFilesError(
                    "HASHMYFILES_RESULT_INVALID", "HashMyFiles 校验结果无法读取。",
                ) from error
            if capture_result.get("item_count") != len(rar_paths):
                raise HashMyFilesError(
                    "HASHMYFILES_RESULT_INVALID", "HashMyFiles 校验结果不完整。",
                )
            _validate_rows(capture_result.get("rows"), rar_paths)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise HashMyFilesError(
            "HASHMYFILES_SCREENSHOT_FAILED", "HashMyFiles 校验截图生成失败。",
        ) from error


def _validate_rows(rows: object, rar_paths: list[Path]) -> None:
    try:
        if not isinstance(rows, list):
            raise ValueError("rows missing")
        expected = sorted((path.name, path.stat().st_size) for path in rar_paths)
        actual = sorted((
            str(row["filename"]),
            int(str(row["size_bytes"]).replace(",", "").replace("\u00a0", "").replace(" ", "")),
        ) for row in rows if isinstance(row, dict))
        valid_md5 = len(rows) == len(rar_paths) and all(
            isinstance(row, dict)
            and len(str(row.get("md5", ""))) == 32
            and all(char in "0123456789abcdefABCDEF" for char in str(row.get("md5", "")))
            for row in rows
        )
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise HashMyFilesError(
            "HASHMYFILES_RESULT_INVALID", "HashMyFiles 校验结果不完整。",
        ) from error
    if actual != expected or not valid_md5:
        raise HashMyFilesError(
            "HASHMYFILES_RESULT_INVALID", "HashMyFiles 校验结果不完整。",
        )


_CAPTURE_SCRIPT = r'''param([string]$JsonPath, [string]$OutputPath, [string]$ResultPath)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class HmfWindow {
  public delegate bool EnumChildProc(IntPtr hwnd, IntPtr lParam);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  [DllImport("user32.dll")] static extern bool EnumChildWindows(IntPtr parent, EnumChildProc callback, IntPtr data);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr hwnd, System.Text.StringBuilder name, int max);
  [DllImport("user32.dll")] static extern IntPtr SendMessageTimeout(IntPtr hwnd, uint msg, IntPtr wParam, IntPtr lParam, uint flags, uint timeout, out IntPtr result);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hwnd, IntPtr after, int x, int y, int cx, int cy, uint flags);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hwnd, int command);
  [DllImport("user32.dll")] public static extern IntPtr SetFocus(IntPtr hwnd);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd, out RECT rect);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool RedrawWindow(IntPtr hwnd, IntPtr rect, IntPtr region, uint flags);
  [DllImport("kernel32.dll")] static extern IntPtr OpenProcess(uint access, bool inherit, uint processId);
  [DllImport("kernel32.dll")] static extern IntPtr VirtualAllocEx(IntPtr process, IntPtr address, uint size, uint allocationType, uint protect);
  [DllImport("kernel32.dll")] static extern bool WriteProcessMemory(IntPtr process, IntPtr address, byte[] buffer, int size, out IntPtr written);
  [DllImport("kernel32.dll")] static extern bool ReadProcessMemory(IntPtr process, IntPtr address, byte[] buffer, int size, out IntPtr read);
  [DllImport("kernel32.dll")] static extern bool VirtualFreeEx(IntPtr process, IntPtr address, uint size, uint freeType);
  [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
  [DllImport("kernel32.dll")] static extern bool IsWow64Process(IntPtr process, out bool wow64);
  [DllImport("kernel32.dll", CharSet=CharSet.Unicode)] static extern IntPtr CreateJobObject(IntPtr attributes, string name);
  [DllImport("kernel32.dll")] static extern bool SetInformationJobObject(IntPtr job, int infoClass, IntPtr info, uint length);
  [DllImport("kernel32.dll")] static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
  public static IntPtr FindDescendant(IntPtr parent, string className) {
    IntPtr found = IntPtr.Zero;
    EnumChildWindows(parent, delegate(IntPtr child, IntPtr data) {
      var name = new System.Text.StringBuilder(128);
      GetClassName(child, name, name.Capacity);
      if (name.ToString() == className) { found = child; return false; }
      return true;
    }, IntPtr.Zero);
    return found;
  }
  public static IntPtr SendSafe(IntPtr window, uint message, IntPtr wParam, IntPtr lParam) {
    IntPtr result;
    if (SendMessageTimeout(window, message, wParam, lParam, 2, 2000, out result) == IntPtr.Zero)
      throw new TimeoutException("HashMyFiles window did not respond");
    return result;
  }
  public static bool ClearSelection(IntPtr list, uint processId) {
    IntPtr process = OpenProcess(0x0038, false, processId);
    if (process == IntPtr.Zero) return false;
    IntPtr remote = VirtualAllocEx(process, IntPtr.Zero, 64, 0x3000, 0x04);
    if (remote == IntPtr.Zero) { CloseHandle(process); return false; }
    byte[] item = new byte[64];
    BitConverter.GetBytes(3u).CopyTo(item, 16); // LVIS_FOCUSED | LVIS_SELECTED mask
    IntPtr written;
    bool ok = WriteProcessMemory(process, remote, item, item.Length, out written);
    if (ok) SendSafe(list, 0x102B, new IntPtr(-1), remote); // LVM_SETITEMSTATE
    VirtualFreeEx(process, remote, 0, 0x8000);
    CloseHandle(process);
    return ok;
  }
  public static string ReadListText(IntPtr list, uint processId, int itemIndex, int subItem) {
    IntPtr process = OpenProcess(0x0038, false, processId);
    if (process == IntPtr.Zero) throw new InvalidOperationException("Cannot open HashMyFiles process");
    IntPtr remote = VirtualAllocEx(process, IntPtr.Zero, 4096, 0x3000, 0x04);
    if (remote == IntPtr.Zero) { CloseHandle(process); throw new InvalidOperationException("Cannot allocate HashMyFiles memory"); }
    try {
      bool wow64;
      if (!IsWow64Process(process, out wow64)) throw new InvalidOperationException("Cannot determine HashMyFiles architecture");
      if (!Environment.Is64BitProcess && Environment.Is64BitOperatingSystem && !wow64)
        throw new PlatformNotSupportedException("32-bit PowerShell cannot inspect 64-bit HashMyFiles");
      bool target64 = IntPtr.Size == 8 && !wow64;
      byte[] nativeItem = new byte[64];
      BitConverter.GetBytes(1u).CopyTo(nativeItem, 0); // LVIF_TEXT
      BitConverter.GetBytes(itemIndex).CopyTo(nativeItem, 4);
      BitConverter.GetBytes(subItem).CopyTo(nativeItem, 8);
      long textAddress = remote.ToInt64() + 128;
      if (target64) {
        BitConverter.GetBytes(textAddress).CopyTo(nativeItem, 24);
        BitConverter.GetBytes(1024).CopyTo(nativeItem, 32);
      } else {
        BitConverter.GetBytes((uint)textAddress).CopyTo(nativeItem, 20);
        BitConverter.GetBytes(1024).CopyTo(nativeItem, 24);
      }
      IntPtr transferred;
      if (!WriteProcessMemory(process, remote, nativeItem, nativeItem.Length, out transferred))
        throw new InvalidOperationException("Cannot prepare HashMyFiles row read");
      SendSafe(list, 0x1073, new IntPtr(itemIndex), remote); // LVM_GETITEMTEXTW
      byte[] text = new byte[2048];
      if (!ReadProcessMemory(process, new IntPtr(textAddress), text, text.Length, out transferred))
        throw new InvalidOperationException("Cannot read HashMyFiles row");
      return System.Text.Encoding.Unicode.GetString(text).TrimEnd('\0');
    } finally {
      VirtualFreeEx(process, remote, 0, 0x8000);
      CloseHandle(process);
    }
  }
  [StructLayout(LayoutKind.Sequential)] struct BasicLimits {
    public long PerProcessUserTime, PerJobUserTime; public uint LimitFlags;
    public UIntPtr MinimumWorkingSet, MaximumWorkingSet; public uint ActiveProcessLimit;
    public IntPtr Affinity; public uint PriorityClass, SchedulingClass;
  }
  [StructLayout(LayoutKind.Sequential)] struct IoCounters {
    public ulong ReadOps, WriteOps, OtherOps, ReadBytes, WriteBytes, OtherBytes;
  }
  [StructLayout(LayoutKind.Sequential)] struct ExtendedLimits {
    public BasicLimits Basic; public IoCounters Io;
    public UIntPtr ProcessMemory, JobMemory, PeakProcessMemory, PeakJobMemory;
  }
  public static IntPtr CreateKillOnCloseJob() {
    IntPtr job = CreateJobObject(IntPtr.Zero, null);
    if (job == IntPtr.Zero) throw new InvalidOperationException("Cannot create HashMyFiles job");
    var limits = new ExtendedLimits(); limits.Basic.LimitFlags = 0x2000;
    int size = Marshal.SizeOf(limits); IntPtr data = Marshal.AllocHGlobal(size);
    try {
      Marshal.StructureToPtr(limits, data, false);
      if (!SetInformationJobObject(job, 9, data, (uint)size)) throw new InvalidOperationException("Cannot configure HashMyFiles job");
    } catch { CloseHandle(job); throw; } finally { Marshal.FreeHGlobal(data); }
    return job;
  }
  public static void AssignToJob(IntPtr job, IntPtr process) {
    if (!AssignProcessToJobObject(job, process)) throw new InvalidOperationException("Cannot contain HashMyFiles process");
  }
  public static void CloseJob(IntPtr job) { if (job != IntPtr.Zero) CloseHandle(job); }
}
'@
$payload = Get-Content -LiteralPath $JsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
$configPath = Join-Path ([IO.Path]::GetDirectoryName($JsonPath)) 'HashMyFiles.capture.cfg'
@"
[General]
MarkOddEvenRows=0
ShowGridLines=0
MarkHashInClipboard=0
MarkIdenticals=0
LiveHashes=1
HashTypes=1
"@ | Set-Content -LiteralPath $configPath -Encoding ASCII
function Quote-Arg([string]$value) { return '"' + $value.Replace('"', '\"') + '"' }
$arguments = @('/cfg', (Quote-Arg $configPath), '/files')
$arguments += @($payload.files | ForEach-Object { Quote-Arg ([string]$_) })
$arguments += @($payload.hash_arguments | ForEach-Object { [string]$_ })
$startInfo = New-Object System.Diagnostics.ProcessStartInfo
$startInfo.FileName = [string]$payload.executable
$startInfo.Arguments = $arguments -join ' '
$startInfo.UseShellExecute = $false
$process = New-Object System.Diagnostics.Process
$process.StartInfo = $startInfo
$started = $false
$job = [HmfWindow]::CreateKillOnCloseJob()
try {
  if (-not $process.Start()) { throw 'HashMyFiles did not start' }
  $started = $true
  [HmfWindow]::AssignToJob($job, $process.Handle)
  $null = $process.WaitForInputIdle(10000)
  $deadline = [DateTime]::UtcNow.AddSeconds([double]$payload.timeout_seconds)
  $window = [IntPtr]::Zero
  while ([DateTime]::UtcNow -lt $deadline -and $window -eq [IntPtr]::Zero) {
    if ($process.HasExited) { throw 'HashMyFiles exited before opening its window' }
    $process.Refresh(); $window = $process.MainWindowHandle
    Start-Sleep -Milliseconds 100
  }
  if ($window -eq [IntPtr]::Zero) { throw 'HashMyFiles window was not found' }
  $list = [HmfWindow]::FindDescendant($window, 'SysListView32')
  if ($list -eq [IntPtr]::Zero) { throw 'HashMyFiles result list was not found' }
  $itemCount = 0; $rows = @(); $resultsComplete = $false
  while ([DateTime]::UtcNow -lt $deadline) {
    if ($process.HasExited) { throw 'HashMyFiles exited before hashing completed' }
    $itemCount = [HmfWindow]::SendSafe($list, 0x1004, [IntPtr]::Zero, [IntPtr]::Zero).ToInt32()
    if ($itemCount -eq [int]$payload.expected_count) {
      $rows = @()
      for ($rowIndex = 0; $rowIndex -lt $itemCount; $rowIndex++) {
        $row = @{
          filename = [HmfWindow]::ReadListText($list, [uint32]$process.Id, $rowIndex, 0)
          md5 = [HmfWindow]::ReadListText($list, [uint32]$process.Id, $rowIndex, 1)
          size_bytes = [HmfWindow]::ReadListText($list, [uint32]$process.Id, $rowIndex, 11)
        }
        $rows += $row
      }
      $resultsComplete = @($rows | Where-Object { ([string]$_.md5) -notmatch '^[0-9a-fA-F]{32}$' }).Count -eq 0
      if ($resultsComplete) { break }
    }
    Start-Sleep -Milliseconds 100
  }
  if (-not $resultsComplete) { throw 'HashMyFiles result is incomplete' }
  for ($column = 0; $column -lt 20; $column++) {
    $null = [HmfWindow]::SendSafe($list, 0x101E, [IntPtr]$column, [IntPtr]::Zero)
  }
  $null = [HmfWindow]::SendSafe($list, 0x101E, [IntPtr]0, [IntPtr]300)
  $null = [HmfWindow]::SendSafe($list, 0x101E, [IntPtr]1, [IntPtr]300)
  $null = [HmfWindow]::SendSafe($list, 0x101E, [IntPtr]11, [IntPtr]145)
  if (-not [HmfWindow]::ClearSelection($list, [uint32]$process.Id)) {
    throw 'HashMyFiles selection state could not be cleared'
  }
  $height = [Math]::Max(230, 150 + ($itemCount * 22))
  $null = [HmfWindow]::SetWindowPos($window, [IntPtr]::Zero, 0, 0, 775, $height, 0x0014)
  $null = [HmfWindow]::ShowWindow($window, 4)
  $null = [HmfWindow]::SetFocus($window)
  $null = [HmfWindow]::RedrawWindow($window, [IntPtr]::Zero, [IntPtr]::Zero, 0x0185)
  Start-Sleep -Milliseconds 300
  $rect = New-Object HmfWindow+RECT
  if (-not [HmfWindow]::GetWindowRect($window, [ref]$rect)) { throw 'HashMyFiles window bounds unavailable' }
  $bitmap = New-Object System.Drawing.Bitmap(($rect.Right - $rect.Left), ($rect.Bottom - $rect.Top))
  $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
  $dc = $graphics.GetHdc()
  try {
    if (-not [HmfWindow]::PrintWindow($window, $dc, 2)) { throw 'HashMyFiles window capture failed' }
  } finally { $graphics.ReleaseHdc($dc) }
  $bitmap.Save($OutputPath, [System.Drawing.Imaging.ImageFormat]::Png)
  $graphics.Dispose(); $bitmap.Dispose()
  @{ item_count = $itemCount; rows = @($rows) } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $ResultPath -Encoding UTF8
} finally {
  if ($started -and -not $process.HasExited) {
    $null = $process.CloseMainWindow()
    if (-not $process.WaitForExit(3000)) {
      $process.Kill()
      $null = $process.WaitForExit(3000)
    }
  }
  $process.Dispose()
  [HmfWindow]::CloseJob($job)
}
'''
