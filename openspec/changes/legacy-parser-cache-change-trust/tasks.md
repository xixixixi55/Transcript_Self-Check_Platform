## 1. Contract and observability foundation

- [ ] 1.1 Add the internal file-change trust states, opaque reason codes, token schema version, and metrics DTOs in `packages/backend/app/repository/` without exposing absolute paths; verify import and architecture-layer checks.
- [ ] 1.2 Define the provider boundary used by both `packages/backend/app/repository/filesystem_identity_repository.py` and `packages/backend/app/repository/report_parse_input_metadata_repository.py`; verify a fake provider can express trusted, changed, and untrusted outcomes.
- [ ] 1.3 Add deterministic synthetic tests for same-size same-stat replacement, file identity replacement, deletion/recreation, read failure, and membership changes in `tests/test_filesystem_identity_repository.py` and `tests/test_report_parse_input_repository.py`.

## 2. Windows NTFS change-token adapter

- [ ] 2.1 Implement the lazy Windows adapter in a new backend repository module under `packages/backend/app/repository/`, using per-file USN data plus volume and Journal identity; verify ordinary authorized synthetic files return stable tokens.
- [ ] 2.2 Map unsupported filesystem, network/mobile/cloud source, permission, API, Journal rebuild, Journal gap, and missing-file conditions to `untrusted` without logging paths; verify reason-code and privacy tests.
- [ ] 2.3 Add Windows integration coverage for in-place overwrite with restored stat metadata, atomic replacement, delete/recreate, file addition/removal, and one-of-many dependency changes; verify no fixed sleep or retry loop is required.
- [ ] 2.4 Add a non-Windows or unavailable-provider test double and verify complete-content fallback remains usable instead of blocking parsing.

## 3. TOCTOU-safe content verification

- [ ] 3.1 Update the content-digest path in `packages/backend/app/repository/filesystem_identity_repository.py` to capture and compare pre-read/post-read identity and change tokens; verify a changing file never publishes a digest.
- [ ] 3.2 Add bounded failure semantics for `input_changed_during_read` and read errors in the parser cache boundary; verify stale cached `InspectionReport` data is never returned.
- [ ] 3.3 Add directory membership validation for candidate and selected dependency sets in `packages/backend/app/repository/report_parse_input_metadata_repository.py`; verify additions, deletions, type changes, and missing directories invalidate safely.

## 4. Integrate both parser cache paths

- [ ] 4.1 Integrate the trust provider into the Legacy dynamic dependency path used by `packages/backend/app/services/report_parser_service.py`; verify unchanged trusted dependencies avoid full content rereads.
- [ ] 4.2 Integrate the same contract into `packages/backend/app/repository/report_parse_input_metadata_repository.py` and `packages/backend/app/repository/report_parse_input_repository.py`; verify both paths produce identical changed/untrusted semantics.
- [ ] 4.3 Preserve the separation between `packages/backend/app/services/report_parsing_cache_service.py` and Archive/Manifest repositories; verify parser cache hits never execute WinRAR or provide archive evidence.
- [ ] 4.4 Add end-to-end parser-cache tests in `tests/test_report_parsing_cache.py`, `tests/test_report_parse_cache_metadata.py`, `tests/test_report_parse_cache_lifecycle.py`, and `tests/test_report_parser_service.py`; verify old fields cannot survive source replacement.

## 5. Cache format and restart boundary

- [ ] 5.1 Add `input_trust_schema` handling to `packages/backend/app/repository/report_parsing_cache_models.py` and `packages/backend/app/repository/report_parsing_cache_repository.py`; verify records without the field require complete verification before reuse.
- [ ] 5.2 Keep process-local tokens transient and require full content verification after service restart; verify restart tests do not trust pre-restart in-memory state.
- [ ] 5.3 Add malformed, old-version, partial-write, and cache-migration tests; verify invalid cache records become misses and parse-cache cleanup does not delete RAR, Manifest, DOCX, or source files.

## 6. Performance and packaged deployment validation

- [ ] 6.1 Add a repository-external or ignored synthetic benchmark harness for 13,000+ dependencies; verify it records dependency count, stat count, token queries, read files/bytes, digest recomputations, parse builds, cold, warm, restart, and single-file-change costs.
- [ ] 6.2 Run the same parser/API call chain against equivalent synthetic inputs and compare the existing approximately 366ms/450–492ms measurements only with matching file counts and cache states; verify no conclusion is drawn from direct-IOCTL versus full-API timings.
- [ ] 6.3 Build the final PyInstaller/EXE form and run ordinary NTFS, permission-denied, unsupported-provider, and API-failure cases; verify fallback parses successfully and diagnostics contain no absolute paths.
- [ ] 6.4 Run targeted parser, archive, Manifest, Word safety-gate, architecture, type, documentation, and repository-asset checks; verify ArchiveContext, WinRAR, Manifest, Word, templates, Shadow, and Canonical remain unchanged.

## 7. Release gate and rollback

- [ ] 7.1 Add a safe configuration switch that disables fast token reuse while retaining complete content verification; verify disabling the fast path cannot reintroduce stat-only cache hits.
- [ ] 7.2 Perform independent code review of the new Level 3 change and inspect the staged allowlist separately from the Phase 1A worktree; verify no Phase 1A file or runtime artifact is included.
- [ ] 7.3 Ask for the required full Harness executor confirmation, run the full Harness only after approval, and record all failures and warnings; verify no unrelated or new failure is hidden.
- [ ] 7.4 Complete manual acceptance for supported and unsupported deployment environments, then mark tasks complete only when the parser-cache correctness and performance contracts are evidenced; rollback by disabling fast reuse or isolating parser-cache records, never by deleting formal archive outputs.
