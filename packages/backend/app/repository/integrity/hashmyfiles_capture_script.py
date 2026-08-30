"""用于原生 HashMyFiles 窗口的嵌入式 Windows 捕获脚本。"""

CAPTURE_SCRIPT = r'''param([string]$JsonPath, [string]$OutputPath, [string]$ResultPath)
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
  static bool TrySend(IntPtr window, uint message, IntPtr wParam, IntPtr lParam, out IntPtr result) {
    return SendMessageTimeout(window, message, wParam, lParam, 2, 5000, out result) != IntPtr.Zero;
  }
  public static bool TryGetItemCount(IntPtr list, out int count) {
    IntPtr result; bool ok = TrySend(list, 0x1004, IntPtr.Zero, IntPtr.Zero, out result);
    count = ok ? result.ToInt32() : 0; return ok;
  }
  public static bool TrySetColumnWidth(IntPtr list, int column, int width) {
    IntPtr result; return TrySend(list, 0x101E, new IntPtr(column), new IntPtr(width), out result);
  }
  public static bool TryClearSelection(IntPtr list, uint processId) {
    IntPtr process = OpenProcess(0x0038, false, processId);
    if (process == IntPtr.Zero) return false;
    IntPtr remote = VirtualAllocEx(process, IntPtr.Zero, 64, 0x3000, 0x04);
    if (remote == IntPtr.Zero) { CloseHandle(process); return false; }
    try {
      byte[] item = new byte[64]; BitConverter.GetBytes(3u).CopyTo(item, 16);
      IntPtr written; if (!WriteProcessMemory(process, remote, item, item.Length, out written)) return false;
      IntPtr result; return TrySend(list, 0x102B, new IntPtr(-1), remote, out result);
    } finally { VirtualFreeEx(process, remote, 0, 0x8000); CloseHandle(process); }
  }
  public static bool TryReadListText(IntPtr list, uint processId, int itemIndex, int subItem, out string value) {
    value = ""; IntPtr process = OpenProcess(0x0038, false, processId);
    if (process == IntPtr.Zero) throw new InvalidOperationException("Cannot open HashMyFiles process");
    IntPtr remote = VirtualAllocEx(process, IntPtr.Zero, 4096, 0x3000, 0x04);
    if (remote == IntPtr.Zero) { CloseHandle(process); throw new InvalidOperationException("Cannot allocate HashMyFiles memory"); }
    try {
      bool wow64;
      if (!IsWow64Process(process, out wow64)) throw new InvalidOperationException("Cannot determine HashMyFiles architecture");
      if (!Environment.Is64BitProcess && Environment.Is64BitOperatingSystem && !wow64)
        throw new PlatformNotSupportedException("32-bit PowerShell cannot inspect 64-bit HashMyFiles");
      bool target64 = IntPtr.Size == 8 && !wow64; byte[] item = new byte[64];
      BitConverter.GetBytes(1u).CopyTo(item, 0); BitConverter.GetBytes(itemIndex).CopyTo(item, 4);
      BitConverter.GetBytes(subItem).CopyTo(item, 8); long textAddress = remote.ToInt64() + 128;
      if (target64) { BitConverter.GetBytes(textAddress).CopyTo(item, 24); BitConverter.GetBytes(1024).CopyTo(item, 32); }
      else { BitConverter.GetBytes((uint)textAddress).CopyTo(item, 20); BitConverter.GetBytes(1024).CopyTo(item, 24); }
      IntPtr transferred;
      if (!WriteProcessMemory(process, remote, item, item.Length, out transferred))
        throw new InvalidOperationException("Cannot prepare HashMyFiles row read");
      IntPtr result;
      if (!TrySend(list, 0x1073, new IntPtr(itemIndex), remote, out result)) return false;
      byte[] text = new byte[2048];
      if (!ReadProcessMemory(process, new IntPtr(textAddress), text, text.Length, out transferred))
        throw new InvalidOperationException("Cannot read HashMyFiles row");
      value = System.Text.Encoding.Unicode.GetString(text).TrimEnd('\0'); return true;
    } finally { VirtualFreeEx(process, remote, 0, 0x8000); CloseHandle(process); }
  }
  [StructLayout(LayoutKind.Sequential)] struct BasicLimits {
    public long PerProcessUserTime, PerJobUserTime; public uint LimitFlags;
    public UIntPtr MinimumWorkingSet, MaximumWorkingSet; public uint ActiveProcessLimit;
    public IntPtr Affinity; public uint PriorityClass, SchedulingClass;
  }
  [StructLayout(LayoutKind.Sequential)] struct IoCounters { public ulong ReadOps, WriteOps, OtherOps, ReadBytes, WriteBytes, OtherBytes; }
  [StructLayout(LayoutKind.Sequential)] struct ExtendedLimits {
    public BasicLimits Basic; public IoCounters Io; public UIntPtr ProcessMemory, JobMemory, PeakProcessMemory, PeakJobMemory;
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
LiveHashes=0
HashTypes=1
"@ | Set-Content -LiteralPath $configPath -Encoding ASCII
function Quote-Arg([string]$value) { return '"' + $value.Replace('"', '\"') + '"' }
function Read-ListValue([IntPtr]$list, [uint32]$processId, [int]$row, [int]$column, [ref]$value) {
  return [HmfWindow]::TryReadListText($list, $processId, $row, $column, $value)
}
function Invoke-WindowAction([scriptblock]$action, [DateTime]$deadline) {
  while ([DateTime]::UtcNow -lt $deadline) {
    if (& $action) { return $true }
    Start-Sleep -Milliseconds 500
  }
  return $false
}
$arguments = @('/cfg', (Quote-Arg $configPath), '/files')
$arguments += @($payload.files | ForEach-Object { Quote-Arg ([string]$_) })
$arguments += @($payload.hash_arguments | ForEach-Object { [string]$_ })
$startInfo = New-Object System.Diagnostics.ProcessStartInfo
$startInfo.FileName = [string]$payload.executable
$startInfo.Arguments = $arguments -join ' '
$startInfo.UseShellExecute = $false
$process = New-Object System.Diagnostics.Process
$process.StartInfo = $startInfo
$started = $false; $job = [HmfWindow]::CreateKillOnCloseJob(); $stage = 'launch'; $failureCode = $null
try {
  if (-not $process.Start()) { throw 'HashMyFiles did not start' }
  $started = $true; [HmfWindow]::AssignToJob($job, $process.Handle)
  $null = $process.WaitForInputIdle(10000)
  $deadline = [DateTime]::UtcNow.AddSeconds([double]$payload.timeout_seconds)
  $window = [IntPtr]::Zero
  while ([DateTime]::UtcNow -lt $deadline -and $window -eq [IntPtr]::Zero) {
    if ($process.HasExited) { $failureCode = 'HASHMYFILES_LAUNCH_FAILED'; throw 'HashMyFiles exited before opening its window' }
    $process.Refresh(); $window = $process.MainWindowHandle; Start-Sleep -Milliseconds 500
  }
  if ($window -eq [IntPtr]::Zero) { $failureCode = 'HASHMYFILES_LAUNCH_FAILED'; throw 'HashMyFiles window was not found' }
  $list = [HmfWindow]::FindDescendant($window, 'SysListView32')
  if ($list -eq [IntPtr]::Zero) { $failureCode = 'HASHMYFILES_LAUNCH_FAILED'; throw 'HashMyFiles result list was not found' }
  $stage = 'hashing'; $itemCount = 0; $rows = @(); $resultsComplete = $false
  $hashPattern = '^[0-9a-fA-F]{' + [string]$payload.hash_digest_length + '}$'
  while ([DateTime]::UtcNow -lt $deadline) {
    if ($process.HasExited) { $failureCode = 'HASHMYFILES_RUN_FAILED'; throw 'HashMyFiles exited before hashing completed' }
    $count = 0
    if (-not [HmfWindow]::TryGetItemCount($list, [ref]$count)) { Start-Sleep -Milliseconds 500; continue }
    $itemCount = $count
    if ($itemCount -eq [int]$payload.expected_count) {
      $hashes = @(); $readable = $true
      for ($rowIndex = 0; $rowIndex -lt $itemCount; $rowIndex++) {
        $hashValue = ''
        if (-not (Read-ListValue $list ([uint32]$process.Id) $rowIndex ([int]$payload.hash_column_index) ([ref]$hashValue))) { $readable = $false; break }
        $hashes += $hashValue
      }
      if ($readable -and @($hashes | Where-Object { ([string]$_) -notmatch $hashPattern }).Count -eq 0) {
        $candidateRows = @(); $readable = $true
        for ($rowIndex = 0; $rowIndex -lt $itemCount; $rowIndex++) {
          $filename = ''; $hashValue = ''; $sizeBytes = ''
          if (-not (Read-ListValue $list ([uint32]$process.Id) $rowIndex 0 ([ref]$filename))) { $readable = $false; break }
          if (-not (Read-ListValue $list ([uint32]$process.Id) $rowIndex ([int]$payload.hash_column_index) ([ref]$hashValue))) { $readable = $false; break }
          if (-not (Read-ListValue $list ([uint32]$process.Id) $rowIndex 11 ([ref]$sizeBytes))) { $readable = $false; break }
          $candidateRows += @{ filename = $filename; hash_value = $hashValue; size_bytes = $sizeBytes }
        }
        if ($readable) { $rows = $candidateRows; $resultsComplete = $true; break }
      }
    }
    Start-Sleep -Milliseconds 500
  }
  if (-not $resultsComplete) { $failureCode = 'HASHMYFILES_TIMEOUT'; throw 'HashMyFiles hashing deadline elapsed' }
  $stage = 'window_capture'; $captureDeadline = [DateTime]::UtcNow.AddSeconds([double]$payload.capture_grace_seconds)
  for ($column = 0; $column -lt 20; $column++) {
    $currentColumn = $column
    if (-not (Invoke-WindowAction { [HmfWindow]::TrySetColumnWidth($list, $currentColumn, 0) } $captureDeadline)) {
      $failureCode = 'HASHMYFILES_WINDOW_UNRESPONSIVE'; throw 'HashMyFiles column layout did not respond'
    }
  }
  $visibleColumns = @(
    @{ column = 0; width = 300 },
    @{ column = [int]$payload.hash_column_index; width = [int]$payload.hash_column_width },
    @{ column = 11; width = 145 }
  )
  foreach ($columnWidth in $visibleColumns) {
    $currentColumn = [int]$columnWidth.column; $currentWidth = [int]$columnWidth.width
    if (-not (Invoke-WindowAction { [HmfWindow]::TrySetColumnWidth($list, $currentColumn, $currentWidth) } $captureDeadline)) {
      $failureCode = 'HASHMYFILES_WINDOW_UNRESPONSIVE'; throw 'HashMyFiles visible columns did not respond'
    }
  }
  if (-not (Invoke-WindowAction { [HmfWindow]::TryClearSelection($list, [uint32]$process.Id) } $captureDeadline)) {
    $failureCode = 'HASHMYFILES_WINDOW_UNRESPONSIVE'; throw 'HashMyFiles selection state did not respond'
  }
  $height = [Math]::Max(230, 150 + ($itemCount * 22))
  $null = [HmfWindow]::SetWindowPos($window, [IntPtr]::Zero, 0, 0, [int]$payload.window_width, $height, 0x0014)
  $null = [HmfWindow]::ShowWindow($window, 4); $null = [HmfWindow]::SetFocus($window)
  $null = [HmfWindow]::RedrawWindow($window, [IntPtr]::Zero, [IntPtr]::Zero, 0x0185)
  Start-Sleep -Milliseconds 300
  $stage = 'screenshot'; $captured = $false
  while ([DateTime]::UtcNow -lt $captureDeadline -and -not $captured) {
    $bitmap = $null; $graphics = $null
    try {
      $rect = New-Object HmfWindow+RECT
      if (-not [HmfWindow]::GetWindowRect($window, [ref]$rect)) { throw 'HashMyFiles window bounds unavailable' }
      $bitmap = New-Object System.Drawing.Bitmap(($rect.Right - $rect.Left), ($rect.Bottom - $rect.Top))
      $graphics = [System.Drawing.Graphics]::FromImage($bitmap); $dc = $graphics.GetHdc()
      try { $captured = [HmfWindow]::PrintWindow($window, $dc, 2) } finally { $graphics.ReleaseHdc($dc) }
      if ($captured) { $bitmap.Save($OutputPath, [System.Drawing.Imaging.ImageFormat]::Png) }
    } catch { $captured = $false } finally {
      if ($null -ne $graphics) { $graphics.Dispose() }
      if ($null -ne $bitmap) { $bitmap.Dispose() }
    }
    if (-not $captured) { Start-Sleep -Milliseconds 500 }
  }
  if (-not $captured) { $failureCode = 'HASHMYFILES_SCREENSHOT_FAILED'; throw 'HashMyFiles window capture failed' }
  @{ status = 'succeeded'; item_count = $itemCount; hash_algorithm = [string]$payload.hash_algorithm; rows = @($rows) } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $ResultPath -Encoding UTF8
} catch {
  if (-not $failureCode) {
    $failureCode = if ($stage -eq 'launch') { 'HASHMYFILES_LAUNCH_FAILED' } elseif ($stage -eq 'screenshot') { 'HASHMYFILES_SCREENSHOT_FAILED' } else { 'HASHMYFILES_RUN_FAILED' }
  }
  @{ status = 'failed'; stage = $stage; error_code = $failureCode } | ConvertTo-Json | Set-Content -LiteralPath $ResultPath -Encoding UTF8
  exit 1
} finally {
  if ($started -and -not $process.HasExited) {
    $null = $process.CloseMainWindow()
    if (-not $process.WaitForExit(3000)) { $process.Kill(); $null = $process.WaitForExit(3000) }
  }
  $process.Dispose(); [HmfWindow]::CloseJob($job)
}
'''
