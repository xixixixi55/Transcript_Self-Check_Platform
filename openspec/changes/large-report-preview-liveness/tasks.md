# Tasks: Large Report Preview Liveness

> Change: `large-report-preview-liveness`
> Level: 3
workflow_level: 3
> Status: `PROPOSED`; implementation and focused/full automated checks for the current repair are complete. Synthetic benchmark, post-repair manual acceptance, and final review gates remain open.
> Scope: preview liveness, parser snapshot/cache identity, in-flight reuse, and deferred full ArchiveContext.
> Explicitly out of scope: Shadow, Canonical, and complete Harness execution.

## Objective and acceptance gates

The implementation is complete only when the requirements in `openspec/changes/large-report-preview-liveness/specs/electronic-inspection-record/spec.md` are covered and the following gates pass:

- first preview of the representative external multi-material report is below 90 seconds with margin;
- valid cache-hit preview is below 15 seconds;
- preview does not build a full ArchiveContext or enumerate the complete input tree;
- same-directory concurrent requests share one expensive parse task, including after a frontend Abort;
- core JSON and actual Parser dependencies are not reopened for a separate fingerprint pass;
- Legacy and New synthetic DTO parity tests pass;
- formal archive preparation still performs complete inventory, readability, path/link, change, full content fingerprint, WinRAR, Manifest, RAR, download, and export validation;
- real report path, case name, business data, generated output, and performance logs remain outside Git and repository documentation;

## Implementation order

Tasks are ordered by architecture layer. Every implementation task is immediately followed by its verification task, as required by the Harness architecture rules.

### Layer 0/1 — Shared contracts and constants

- [x] **T1 — Define explicit preview/archive readiness contracts**
  - Requirements: REQ-PREVIEW-SNAPSHOT-001, REQ-ARCHIVE-LIFECYCLE-001, REQ-FRONTEND-LIVENESS-003.
  - Files: `packages/shared/types/archive.ts`, `packages/shared/types/index.ts`, `packages/shared/constants/index.ts`.
  - Add a readiness status that distinguishes `not_prepared`, `preparing`, `ready`, and `failed`; define the nullable/explicit shell summary; preserve `InspectionReport`, `rar_info`, `ArchiveManifest`, and Legacy DTO fields.
  - Add only the source-neutral archive-preparation endpoint constant if the Controller design selects a new route.
  - Keep API names compatible with existing camelCase/snake_case boundary conventions.

- [x] **T2 — Verify shared contract compatibility**
  - Requirements: REQ-PREVIEW-SNAPSHOT-004, REQ-ARCHIVE-LIFECYCLE-001.
  - Files: `packages/shared/types/*.ts` tests/typecheck coverage and any existing archive type tests.
  - Verify existing consumers compile, formal `ArchiveManifest` is unchanged, and readiness cannot be represented only by `idle`.
  - Run the targeted shared typecheck only; do not run the complete Harness gate in this phase.

### Layer 10/11/12 — Frontend preview and archive lifecycle UI

- [x] **T3 — Make preview archive preparation passive**
  - Requirements: REQ-FRONTEND-LIVENESS-001, REQ-FRONTEND-LIVENESS-002.
  - Files: `packages/frontend/src/hooks/useArchivePreparation.ts`, `packages/frontend/src/hooks/useReportParser.ts`.
  - Remove the effect-driven archive execution/polling side effect from report load and disc-number changes. Keep explicit preparation callable for a later user action, with independent loading, Abort, error, retry, and stale-attempt handling.
  - Keep the existing preview timeout value; do not extend it.

- [x] **T4 — Test passive preview hook and retry cleanup**
  - Requirements: REQ-FRONTEND-LIVENESS-001, REQ-FRONTEND-LIVENESS-002, REQ-PARSE-INFLIGHT-002.
  - Files: `packages/frontend/src/hooks/useArchivePreparation.test.tsx`, `packages/frontend/src/hooks/useReportParser.test.ts`.
  - Add tests proving report load does not call archive execution or create a polling loop, explicit preparation has separate loading/error cleanup, timeout/network cancellation ends preview loading, and stale responses cannot replace a newer attempt.
  - Use mocked HTTP responses and synthetic report values only.

- [x] **T5 — Display explicit archive-not-prepared state and preserve export gate**
  - Requirements: REQ-ARCHIVE-LIFECYCLE-001, REQ-FRONTEND-LIVENESS-003.
  - Files: `packages/frontend/src/pages/RecordGeneratePage.tsx`, existing archive status component(s), `packages/frontend/src/hooks/useRecordExport.ts` only if required by the contract.
  - Show that review is available while archive preparation is not ready; do not show `idle` as a ready state. Keep formal export blocked until a ready context and validated Manifest exist.

- [x] **T6 — Test review status and export boundary**
  - Requirements: REQ-FRONTEND-LIVENESS-001, REQ-FRONTEND-LIVENESS-003, REQ-CHANGE-BOUNDARIES-001.
  - Files: existing page/archive status tests, or new tests adjacent to the changed component.
  - Verify report editing remains available, no archive request starts automatically, not-prepared status is visible, and export is blocked with an actionable message.

### Layer 20 — Controlled filesystem and parser input repository

- [x] **T7 — Implement request input snapshot and dependency index**
  - Requirements: REQ-PREVIEW-SNAPSHOT-002, REQ-PREVIEW-SNAPSHOT-003, REQ-PARSE-CACHE-001.
  - Files: new `packages/backend/app/repository/report_parse_input_repository.py`; existing `packages/backend/app/repository/html_parser.py` and `packages/backend/app/repository/filesystem_identity_repository.py` only where the snapshot boundary requires integration.
  - Implement one-time core JSON loading, format result reuse, ordered device rows, evidence-directory mapping, explicit device metadata candidate selection, and dependency records that capture path metadata and content digest during the same read.
  - Reject unsafe/absolute dependency paths. Do not recurse through media, attachment HTML, navigation payloads, or unrelated JSON. Do not expose absolute paths in returned/public data.
  - Keep Legacy and New parser adapters compatible; do not silently introduce an unbounded fallback scan.

- [x] **T8 — Test snapshot reads and candidate/dependency scope**
  - Requirements: REQ-PREVIEW-SNAPSHOT-002, REQ-PREVIEW-SNAPSHOT-003, REQ-PREVIEW-SNAPSHOT-004.
  - Files: new `tests/test_report_parse_input_repository.py`; focused additions to `tests/test_html_parser.py` and `tests/test_filesystem_identity_repository.py`.
  - Use synthetic Legacy and New fixtures to assert each core JSON is loaded once, device directory resolution is reused, candidate files are bounded/explicit, media and unrelated JSON are not opened, dependency paths are relative, and captured metadata/digests are stable.
  - Add DTO parity assertions against the existing parser behavior using synthetic fixtures.

- [x] **T9 — Implement metadata-first dependency validation**
  - Requirements: REQ-PARSE-CACHE-001, REQ-PARSE-CACHE-002, REQ-PARSE-CACHE-003.
  - Files: `packages/backend/app/repository/report_parsing_cache_repository.py`, `packages/backend/app/services/report_parsing_cache_service.py`, and the snapshot/identity repository from T7 where needed.
  - Store the dependency manifest with the existing cache payload/version/LRU record. Validate paths, size, mtime, and stable identity first; reuse unchanged digests; recalculate only changed/new dependencies; invalidate when candidate membership changes.
  - Preserve atomic writes, corruption cleanup, LRU behavior, cache clear isolation, and opaque cache keys. Do not touch ArchiveManifest/RAR/Word outputs.

- [x] **T10 — Test cache invalidation and one-pass behavior**
  - Requirements: REQ-PARSE-CACHE-001, REQ-PARSE-CACHE-002, REQ-PARSE-CACHE-003.
  - Files: `tests/test_report_parsing_cache.py`, `tests/test_report_parser_service.py`, and repository tests adjacent to the changed modules.
  - Assert first parse combines read/parse/digest work, cache hit does not reopen unchanged dependencies, changed dependency metadata/content invalidates, unrelated media/attachment changes do not, candidate additions invalidate, malformed/failed writes clean up, and cache clear does not touch archive lifecycle files.
  - Add read counters to prove the old “fingerprint then Parser” duplicate pass is absent.

### Layer 21 — Parser orchestration and runtime lifecycle

- [x] **T11 — Integrate snapshot parsing with report Parser and cache**
  - Requirements: REQ-PREVIEW-SNAPSHOT-001 through REQ-PREVIEW-SNAPSHOT-004, REQ-PARSE-CACHE-001.
  - Files: `packages/backend/app/services/report_parser_service.py`, `packages/backend/app/repository/report_parse_input_repository.py`, and `packages/backend/app/services/report_parsing_cache_service.py`.
  - Make the Parser accept one request snapshot, reuse core/config/device data, parse each actual dependency once, register the dependency manifest, and return the unchanged Legacy-compatible report result. Keep `compress` deprecated and non-operative for folder preview.
  - Do not add ArchiveContext inventory or WinRAR work to the parser service.

- [x] **T12 — Test Parser phase reuse and DTO parity**
  - Requirements: REQ-PREVIEW-SNAPSHOT-001 through REQ-PREVIEW-SNAPSHOT-004.
  - Files: `tests/test_report_parser_service.py`, new focused parser snapshot tests if needed.
  - Assert public JSON read counts, per-device candidate read counts, no whole-report recursion, Legacy/New DTO parity, `rar_info` compatibility, failure safety, and no Shadow/Canonical calls.

- [x] **T13 — Implement bounded same-directory in-flight registry**
  - Requirements: REQ-PARSE-INFLIGHT-001 through REQ-PARSE-INFLIGHT-003.
  - Files: `packages/backend/app/services/report_parse_inflight_service.py` and `packages/backend/app/services/report_parser_service.py` integration.
  - Acquire by normalized opaque directory identity before dependency discovery. Share a bounded future/task, detach cancelled waiters without cancelling the shared work, publish one result/error, enforce capacity and maximum lifetime, and remove completed/failed entries safely.
  - Ensure the existing cache-store lock remains a consistency guard rather than the first expensive-work deduplicator. Do not log raw paths.

- [x] **T14 — Test in-flight joining, cancellation, capacity, and failure cleanup**
  - Requirements: REQ-PARSE-INFLIGHT-001 through REQ-PARSE-INFLIGHT-003.
  - Files: new `tests/test_report_parse_inflight_service.py`, additions to `tests/test_report_parser_service.py`.
  - Use barriers/fake builders and synthetic directories to assert two same-key requests run one builder, follower cancellation does not start a second builder, different keys are independent, capacity is bounded, failures are retryable, and no permanent entry remains.

- [x] **T15 — Split context shell from full ArchiveContext materialization**
  - Requirements: REQ-ARCHIVE-LIFECYCLE-001 through REQ-ARCHIVE-LIFECYCLE-003.
  - Files: `packages/backend/app/services/archive_runtime_models_service.py`, `packages/backend/app/services/archive_runtime_service.py`, `packages/backend/app/services/archive_source_runtime_service.py`, and `packages/backend/app/services/archive_execution_service.py`.
  - Add an opaque, short-lived authorized shell with explicit readiness and no inventory; make preview use the shell only. Add an explicit source-neutral preparation operation that revalidates authorization, builds complete inventory, and upgrades/publishes a full context.
  - Preserve formal `verify_input_inventory`, full input content fingerprint, WinRAR planning/execution, RAR integrity, Manifest, download, and export validation. A shell and parse cache must be rejected as formal evidence.

- [x] **T16 — Test shell readiness and formal archive safety**
  - Requirements: REQ-ARCHIVE-LIFECYCLE-001 through REQ-ARCHIVE-LIFECYCLE-003, REQ-CHANGE-BOUNDARIES-001, REQ-CHANGE-BOUNDARIES-002.
  - Files: `tests/test_archive_runtime_service.py`, `tests/test_archive_source_runtime_service.py`, and `tests/test_archive_execution_service.py`.
  - Assert preview shell creation does not call full inventory, shell execution is rejected, explicit preparation builds current inventory, source changes/links/unreadable files fail, and all formal archive/Manifest/RAR gates remain active. Assert no Shadow or Canonical behavior is introduced.

### Layer 22/23 — HTTP boundary

- [x] **T17 — Return preview without full context and expose explicit preparation boundary**
  - Requirements: REQ-PREVIEW-SNAPSHOT-001, REQ-ARCHIVE-LIFECYCLE-001, REQ-ARCHIVE-LIFECYCLE-002.
  - Files: `packages/backend/app/controllers/record_controller.py`, `packages/backend/app/controllers/archive_controller.py`, `packages/backend/app/routes/__init__.py` only if a dedicated preparation route is selected.
  - Remove synchronous full `create_archive_context` from the preview endpoint. Return the report plus explicit readiness/shell state. Map shell-not-ready, capacity, timeout, and parser failures to safe stable errors without paths or report data.
  - Add only the preparation request needed to materialize the full context from the authorized report-directory source.

- [x] **T18 — Test controller response and archive boundary**
  - Requirements: REQ-PREVIEW-SNAPSHOT-001, REQ-ARCHIVE-LIFECYCLE-001 through REQ-ARCHIVE-LIFECYCLE-003, REQ-FRONTEND-LIVENESS-003.
  - Files: `tests/test_record_controller.py` and `tests/test_shadow_pipeline.py` (archive-controller integration cases).
  - Assert preview response returns before inventory in mocked integration, explicit not-prepared state is not `idle`, old report-only fields remain compatible, shell cannot export, preparation creates a full context, and errors do not leak paths/content.

## Cross-layer verification and acceptance

- [ ] **T19 — Add synthetic performance/read-count benchmark** [DEFERRED]
  - Requirements: REQ-ACCEPTANCE-001, REQ-PARSE-CACHE-001, REQ-PARSE-INFLIGHT-001.
  - Files: new synthetic benchmark/test adjacent to the backend test suite; no real report or generated output.
  - Assert preview avoids full inventory, core JSON reads are one per task, same dependency is not read once for fingerprint and again for Parser, cache hit meets the synthetic budget, and same-key concurrency runs one expensive task.
  - Status note: focused read-count, cache, and in-flight tests exist, but no single dedicated T19 benchmark record has been identified. Keep this task open until explicit synthetic benchmark evidence is available.

- [x] **T20 — Run scoped verification and manual acceptance preparation**
  - Requirements: all requirements above.
  - Files: no production file; update this tasks file only as tasks complete.
  - Run targeted backend/frontend tests, `lint:arch`, typecheck, `git diff --check`, and repository asset checks as appropriate. Prepare the human-only external report validation checklist without recording its path, case data, logs, or outputs. Do not run `verify:full` until implementation, manual acceptance, and independent review are complete and the user is asked whether they want to execute the full Harness gate.

- [x] **T21 — Preserve all material numbers in Legacy process/result projection**
  - Requirements: REQ-PREVIEW-SNAPSHOT-004.
  - Files: `packages/backend/app/services/report_parser_service.py`, `tests/test_report_parser_service.py`.
  - Keep the existing Legacy DTO shape while projecting the ordered `evidence_list` into process-step and result strings. Add a synthetic multi-material regression test; retain single-material wording and do not alter archive, frontend, template, Shadow, or Canonical behavior.

- [x] **T22 — Allow report-only Word export without archive preparation**
  - Requirements: REQ-FRONTEND-LIVENESS-003, REQ-ARCHIVE-LIFECYCLE-003.
  - Files: `packages/backend/app/controllers/record_controller.py`, `packages/frontend/src/hooks/useRecordExport.ts`, `packages/frontend/src/pages/RecordGeneratePage.tsx`, `packages/frontend/src/components/ReviewActionBar.tsx`, and their focused tests.
  - Decouple explicit Word report generation from archive preparation while preserving all report validation. Keep the existing complete inventory, Manifest, RAR, WinRAR, path/link, and change gates whenever formal archive identifiers are supplied. Partial archive identifiers fail safely; no archive or Shadow task is started by report-only export.

- [x] **T23 — Preserve single-material device display names in the Legacy-compatible DTO**
  - Requirements: REQ-PREVIEW-SNAPSHOT-004.
  - Files: `packages/backend/app/services/report_parser_service.py`, `tests/test_report_parser_service.py`.
  - Keep `device_name` as the normalized model display value, preserve `model` and `device_type` semantics, invalidate stale parse caches, and cover synthetic Legacy/New single-material projections without changing the shared DTO shape.

- [x] **T24 — Part 1: Separate mutable revisions from archive ownership**
  - Requirements: REQ-ARCHIVE-LIFECYCLE-004.
  - Files: `packages/backend/app/services/archive_worker_service.py`, `packages/backend/app/services/archive_runtime_coordinator_service.py`.
  - Treat `process_tree_id` plus the bound attempt ID as the ownership identity. Converge cancellation before worker start and in the coordinator fallback without allowing `cancelling` to be overwritten by `failed_retryable`.

- [x] **T25 — Verify the preparation/cancellation race fix**
  - Requirements: REQ-ARCHIVE-LIFECYCLE-004.
  - Files: `tests/test_archive_worker_service.py`, `tests/test_archive_runtime_lifecycle.py`.
  - Reproduce cancellation after claim and during blocked item preparation; assert task cancellation and `ARCHIVE_CANCELLED`. Replace the owner token separately and assert the stale worker still receives `ARCHIVE_TASK_OWNERSHIP_LOST`.

- [x] **T26 — Part 2: Expose and interrupt slow full-inventory preparation**
  - Requirements: REQ-ARCHIVE-LIFECYCLE-002, REQ-ARCHIVE-LIFECYCLE-004.
  - Files: archive runtime coordinator/source/context services and `packages/backend/app/repository/archive_input_repository.py`.
  - Advance the claimed task to `inventory` before full traversal and propagate a cooperative cancellation callback through context preparation into directory enumeration. Preserve all formal archive gates and inventory publication rules.

- [x] **T27 — Verify inventory visibility and cooperative cancellation**
  - Requirements: REQ-ARCHIVE-LIFECYCLE-004, REQ-ACCEPTANCE-002.
  - Files: `tests/test_archive_input_repository.py`, `tests/test_archive_runtime_lifecycle.py`, existing archive runtime/source/worker tests.
  - Assert a blocked preparation is already at the inventory milestone, traversal stops at the cancellation boundary, and the focused archive lifecycle suite remains green.

## Post-implementation gates

- [x] Independent code review completed for Level 3. Independent review passed after the stale-owner/attempt-binding guard and integration regression were added.
- [ ] Human manual acceptance completed against the external multi-material report without adding sensitive artifacts. The earlier evidence predates T24-T27; repeat the archive-stage/cancellation acceptance without recording sensitive paths, business data, generated output, or performance logs. [DEFERRED]
- [ ] Full Harness execution completed and passed; the earlier run predates T24-T27 and must not be reused as current evidence. [DEFERRED]
- [ ] No commit or push is performed unless separately requested. [N/A]
