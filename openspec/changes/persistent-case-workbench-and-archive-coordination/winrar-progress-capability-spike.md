# Phase 3 WinRAR progress capability spike

> Initial spike: 2026-07-30, RAR 5.90
> Version/adapter decision: 2026-07-30, RAR 7.23 x64
> Input classification: `SYNTHETIC/TEST/FIXTURE`
> Decision: **unsupported; T011 remains blocked**

## Scope and isolation

Both spikes used only generated synthetic files. The 7.23 Windows x64 package
was downloaded from the official RARLAB download endpoint into a system
temporary directory, verified, and unpacked as an SFX archive with the existing
RAR CLI. The installer was not executed. No existing WinRAR file, file
association, registry value, environment variable, application setting, or
formal archive output was changed.

No installer, executable, raw console log, temporary RAR, real report, case
data, machine path, or persistent configuration is stored in the repository.

## 7.23 executable evidence

| Item | Sanitized evidence |
|---|---|
| Package | Official `winrar-x64-723.exe`, 3,775,056 bytes |
| Package SHA-256 | `8ff0daf3ed564cc743c0e23ff2e253997ffc74460f9673f0b6dd037b2db4ce7b` |
| Package signature | Valid, signer `win.rar GmbH` |
| Executable | `Rar.exe` |
| File/product version | `7.23.0` |
| Architecture | PE machine `0x8664`, x64 |
| Executable SHA-256 | `f561764bc3e9ed208744321a89a819b562edeaf06e203c02a06976121fda1991` |
| Executable signature | Valid, signer `win.rar GmbH` |

## Capture and parser contract tested

- Capture method: ordinary binary stdout/stderr pipes, matching the current
  production `subprocess.Popen(..., stdout=PIPE, stderr=PIPE)` shape.
- PTY/ConPTY was not used. The spike therefore does not add a terminal
  emulation dependency or infer state from rendered screen cells.
- stdout and stderr were retained as raw bytes for in-memory analysis.
  All 7.23 samples in this spike were ASCII; stderr was empty.
- Candidate parser: raw byte regex `(?<!\d)(\d{1,3})%`.
- The parser does not consume file names, localized messages, archive names,
  or other prose. Raw logs are not persisted; sanitized byte counts, hashes,
  percentage counts, regressions, terminal values, and return codes are kept.

## Exact command shapes

```text
Rar.exe a -r -y -idn <archive> <single-file>
Rar.exe a -r -y -idn <archive> <input-root>
Rar.exe a -r -y -idn -v8388608b <archive> <input-root>
Rar.exe a -r -y -idn <archive> SYNTHETIC_MISSING_*
Rar.exe a -r -y -idn -m5 <archive> SYNTHETIC_CANCEL_FIXTURE.bin
Rar.exe a -r -y -inul <archive> <input-root>
```

The normal multi-file input contained deterministic 1 MiB, 6 MiB, and 18 MiB
files. The 8 MiB volume limit guaranteed multiple volumes. Every normal case
was repeated twice with the same input bytes. Cancellation used a separate
128 MiB synthetic file and `Popen.kill()` after 0.5 seconds.

## 7.23 results

| Scenario | Repeated raw percentage evidence | stdout/stderr | Result |
|---|---|---|---|
| Single file | 11 samples per run; `100 -> 22` in both runs; terminal 100 | 299/0 bytes per run, ASCII | Repeatable but not non-decreasing |
| Multiple files | 16 samples per run; `28 -> 20` and `100 -> 44` in both runs; terminal 100 | 338/0 bytes per run, ASCII | Repeatable but not non-decreasing |
| Multiple volumes | 11 samples per run; `28 -> 20` in both runs; terminal 100 | 480/0 bytes per run, ASCII | Repeatable but not non-decreasing |
| Missing input | No percentage; return code 10 | 223/0 bytes, ASCII | Reliably failed; did not report 100 |
| Forced cancellation | Terminal sample 7; return code 1 | 228/0 bytes, ASCII | Reliably interrupted; did not report 100 |
| Legacy `-inul` | No percentage; return code 0 | 0/0 bytes | Successful and silent |

Adding the documented `-qo-` switch to disable Quick Open information did not
remove the repeatable regressions. Ordinary pipe delivery was sufficient to
observe early samples and cancel the process, but it did not change the raw
counter semantics.

## Decision

RAR 7.23 x64 with `-idn` is rejected as the Phase 3 machine-progress adapter.
Although the official switch hides archived names and preserves a total
percentage, the complete raw process stream contains repeatable counter
resets in single-file, multi-file, and multi-volume runs. The stream therefore
does not satisfy the repository contract that normal task progress be
non-decreasing.

The implementation must not make this signal appear valid by taking the
maximum, clamping, smoothing, dropping post-100 samples, selecting only a
convenient pass, or deriving a replacement percentage from time, input bytes,
file counts, or output size. Existing Legacy `-inul` execution remains
unchanged and compatible.

T011 remains blocked. The next bounded adaptation to validate is a Windows
ConPTY spike for the same signed 7.23 `Rar.exe -idn` command. It must capture
stream timing and terminal-state semantics without discarding genuine
counter transitions, prove non-decreasing progress in all required scenarios,
and preserve reliable exit/cancellation classification. Adopting it would add
a Windows-specific pseudo-console/process-control dependency and ownership
boundary, so it requires a separate successful spike before any production
code or shared contract is introduced. If ConPTY exposes the same resets, the
next decision must seek a vendor-supported structured callback/API or retain
stage-only status with no WinRAR percentage; neither is implemented here.

## Reproduction

```powershell
python scripts/probe_winrar_progress.py --executable "<isolated>\Rar.exe"
python -m pytest tests/test_winrar_progress_capability_spike.py -q
```

The probe output is sanitized and never includes raw console output, absolute
paths, external input names, or generated artifacts.
