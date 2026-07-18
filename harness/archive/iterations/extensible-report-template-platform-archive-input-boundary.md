# Iteration: archive input authorization boundary

- Date: 2026-07-19
- Change: `extensible-report-template-platform`
- Scope: fixed configured input roots, reserved exact-directory grants, opaque archive context lifecycle, path/link/output isolation, frontend stable diagnostics.

## Problem → cause → feedback

- Problem: existing folder parsing trusted a client-supplied `report_dir`, while the business must support案件目录分散在不同磁盘和父目录。
- Cause: there was no explicit authorization object between directory selection and archive execution; the runtime context also collapsed missing, expired, and busy states into one error.
- Feedback: `UPLOAD_BASE` plus `BIJI_ALLOWED_INPUT_ROOTS` now authorizes only strict real subdirectories. A future trusted local bridge has a one-use short-lived exact-directory grant model, but no ordinary HTTP endpoint can mint one. `report_dir` is deprecated context creation input; all later stages use only `archive_context_id`.

## Verification

- Backend: `241 passed, 2 skipped`; archive security/execution precision set: `81 passed, 2 skipped`.
- Frontend: `16 files, 87 passed`.
- Architecture lint, typecheck, quick docs, strict docs and strict OpenSpec validation passed.
- Real WinRAR smoke acceptance passed with installed `rar.exe` 5.90: two synthetic input files, single-volume `.part1.rar`, no residual `.rar`, first-volume integrity test, non-zero size, streaming MD5, manifest filename match and staging cleanup. Only sanitized facts were reported; existing output and real case directories were untouched.

## Boundary retained for later work

- Contexts are intentionally in-memory for this iteration; service restart requires re-parse.
- Fixed roots are production-usable; exact-directory grants remain a security model only until a trusted local picker/desktop bridge is connected. Ordinary HTTP paths outside configured roots remain rejected.
- Expiring in-memory manifest metadata never deletes a published successful archive; final publication directories are independent of context cleanup.
- No Word attachment consumption of `ArchiveManifest`, canonical cutover, Shadow end-to-end wiring, or OpenSpec archive was performed.
