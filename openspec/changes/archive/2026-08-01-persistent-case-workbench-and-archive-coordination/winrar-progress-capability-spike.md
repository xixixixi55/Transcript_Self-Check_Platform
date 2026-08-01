# Phase 3 WinRAR progress capability spike

> Initial spike: 2026-07-30, RAR 5.90
> Version/adapter decision: 2026-07-30, RAR 7.23 x64
> ConPTY adapter spike: 2026-07-30, RAR 7.23 x64
> Input classification: `SYNTHETIC/TEST/FIXTURE`
> Capability decision: **continuous WinRAR CLI percentage unsupported**
> Product adaptation: **`workflow_milestone`; prerequisite complete, T011 unblocked but not started**

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

## Ordinary-pipe capture and parser contract tested

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

## ConPTY adapter spike

The same signed, isolated RAR 7.23 x64 executable and deterministic synthetic
input sizes were tested through a native Windows ConPTY host. The host uses
anonymous synchronous input/output pipes, `CreatePseudoConsole`, and
`PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE`. It creates the child suspended, assigns
it to a Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, resumes it, drains
ConPTY output on a separate reader thread, and uses `TerminateJobObject` for
forced cancellation. No permanent runtime dependency or production integration
was added.

ConPTY output was captured as raw bytes and decoded strictly as UTF-8 for this
signed executable. The terminal model handles carriage return, line feed,
backspace, CSI cursor-left/right/absolute-column and erase-to-end updates, plus
OSC title records. Percent samples are taken from the line's current visible
state when WinRAR writes `%`; file names and localized prose are not parsed.
No historical maximum, clamping, smoothing, filtering, or estimation is used.

The exact WinRAR command shapes were unchanged from the ordinary-pipe spike.
ConPTY produced VT screen initialization/cursor sequences and an OSC title.
WinRAR percentage updates used carriage-return line replacement, not an
append-only record stream or backspace replacement. The observed normal-run
control counts contained no backspaces:

| Scenario | Sanitized terminal evidence per repeated run | Current-state result |
|---|---|---|
| Single file | 400 bytes, UTF-8; CR 15, LF 8, CSI 8, OSC 1; 8 samples | `100 -> 22` in both runs; terminal 100 |
| Multiple files | 420 bytes, UTF-8; CR 19, LF 8, CSI 8, OSC 1; 12 samples | `28 -> 20`, `100 -> 44` in both runs; terminal 100 |
| Multiple volumes | 626 bytes, UTF-8; CR 21, LF 11, CSI 16, OSC 1; 10 samples | `28 -> 20` in both runs; terminal 100 |
| Missing input | 384 bytes, UTF-8; return code 10; no percentage | Failed without reporting 100 |
| Forced cancellation | 367 bytes, UTF-8; terminal 4; return code 1 | Job tree terminated; did not report 100 |
| Legacy ordinary pipe `-inul` | 0/0 stdout/stderr bytes; return code 0 | Successful and silent |

Each normal case used the same input bytes twice. Percentage sequences,
regression boundaries, byte counts, and terminal control counts were identical
between repetitions. Raw-byte hashes differed because each run used a distinct
synthetic output archive name; no raw terminal stream or generated archive was
retained. Every successful run reached 100, while failure and forced
cancellation did not. Exit codes and the Job Object cancellation boundary
reliably distinguished success, failure, and interruption.

`-idn` suppressed file-name display as documented, but the visible percentages
cannot be classified as one total-progress counter: a completed-looking 100 is
followed by a lower value in both single-file and multi-file runs. The spike
therefore rejects the premise that every remaining percentage token represents
only aggregate task progress.

## Decision

RAR 7.23 x64 with `-idn` is rejected as the Phase 3 machine-progress adapter
under both ordinary pipes and ConPTY. Parsing ConPTY's current visible terminal
state preserves the same repeatable counter resets in single-file, multi-file,
and multi-volume runs. The resets are therefore WinRAR terminal-state
transitions, not an ordinary-pipe framing artifact. The signal does not satisfy
the repository contract that normal task progress be non-decreasing.

The implementation must not make this signal appear valid by taking the
maximum, clamping, smoothing, dropping post-100 samples, selecting only a
convenient pass, or deriving a replacement percentage from time, input bytes,
file counts, or output size. Existing Legacy `-inul` execution remains
unchanged and compatible.

The strict true-percentage contract is not implementable from the tested
WinRAR CLI output on RAR 5.90 or signed RAR 7.23 x64 through either ordinary
pipes or ConPTY.

The subsequent Phase 3 product/architecture decision selects the stage-only
alternative. Phase 3 uses fixed, persisted `workflow_milestone` values that
advance only when real inventory, preflight, WinRAR, integrity, MD5, Manifest,
and formal-completion boundaries are entered or passed. WinRAR execution stays
at its fixed milestone with an indeterminate activity treatment; no continuous
CLI percentage is parsed or inferred.

This closes the version/adapter prerequisite and unblocks T011 without marking
T011 or later implementation tasks complete. A production ConPTY adapter is
not adopted. WinRAR, RAR volume behavior, Legacy explicit compression, Manifest
authority, and all archive safety gates remain unchanged.

## Reproduction

```powershell
python scripts/probe_winrar_progress.py --executable "<isolated>\Rar.exe"
python scripts/probe_winrar_conpty_progress.py --executable "<isolated>\Rar.exe"
python -m pytest tests/test_winrar_progress_capability_spike.py -q
```

The probe output is sanitized and never includes raw console output, absolute
paths, external input names, or generated artifacts.
