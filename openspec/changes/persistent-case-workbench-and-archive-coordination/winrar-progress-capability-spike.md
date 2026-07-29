# Phase 3 WinRAR progress capability spike

> Date: 2026-07-30
> Input classification: `SYNTHETIC/TEST/FIXTURE`
> Result: **not passed**

## Scope

This spike tested the currently discovered formal console executable only. It
did not use case data, report directories, formal RAR/Manifest/Word artifacts,
machine configuration files, or `word_templates/template.docx`.

## Environment and signal source

- Executable: `Rar.exe` (the absolute installation path is intentionally not
  recorded).
- Reported version: RAR 5.90 x64.
- Candidate signal: human-oriented percentages written to stdout with
  backspace-overwrite control characters when `-inul` is absent.
- Current Legacy execution: `-inul` remains enabled and emits no stdout/stderr
  progress signal.

## Synthetic observations

Two repeated runs used deterministic synthetic files of 4 MiB, 12 MiB, and
24 MiB. Both runs completed, but each raw percentage stream contained
unlabelled regressions including `10 -> 2`, `40 -> 12`, and `100 -> 42`.
The localized console stream does not identify which counter or pass each
percentage represents, so taking the latest value would regress and taking the
maximum would report 100% before execution actually completes.

The existing Legacy `-inul` command completed successfully with empty
stdout/stderr. A deliberately missing synthetic input returned non-zero exit
code 10 and no percentage tokens. Failure therefore remains detectable by the
process result, but the tested console output is not a stable structured
progress contract.

## Decision

The current RAR 5.90 console output does not pass the Phase 3 requirement for a
stable, explainable actual percentage signal. Phase 3 true-percentage
implementation and acceptance remain blocked until a supported WinRAR version
or an explicitly approved adapter is selected and proven by a new spike.

During that decision, the existing Legacy explicit archive path remains
unchanged and usable. No time-based estimate, animation, output-file size, or
maximum-seen console percentage may be presented as actual progress.

## Reproduction and regression evidence

Run:

```powershell
python scripts/probe_winrar_progress.py
python -m pytest tests/test_winrar_progress_capability_spike.py -q
```

The probe returns only sanitized capability evidence: executable name, version,
sample/regression counts, terminal percentages, silent Legacy compatibility,
and failure return code. It does not return raw localized output, absolute
paths, input names from external data, or generated artifacts.
