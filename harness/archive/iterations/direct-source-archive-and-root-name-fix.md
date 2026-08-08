# Iteration: direct source archive and root-name fix

- Date: 2026-08-08
- Change: `openspec/changes/direct-source-archive-and-root-name-fix`
- Scope: direct-source WinRAR execution, source-change metadata gates, archive-root preservation, and user warnings during the compression workflow.

## Problem → cause → feedback

- Problem: archives created from a sealed snapshot could expose generated internal paths such as `.i/s...` after extraction, and copying the complete source into a snapshot added a second full-data pass before compression.
- Cause: the executor selected an absolute snapshot path when the generated snapshot basename differed from the original source basename. The safety model also assumed every new attempt had a sealed snapshot.
- Feedback: new attempts now compress the authorized source directory directly, with the source parent as WinRAR's working directory and the source basename as the only input argument. Metadata inventory is checked before and after WinRAR; detected changes fail with `ARCHIVE_INPUT_CHANGED`, clean staging, and prevent publication. The UI requires confirmation and continuously warns users not to modify, move, delete, or write into the source while compression is active.
- Manual acceptance exposed three follow-up defects. First, disc-number autosave advanced the draft from revision 5 to 7 during WinRAR, so the stage-8 publication fence rejected the stale attempt and a generic catch misreported it as `ARCHIVE_PARTS_INVALID`. Second, two hot-reload backend processes shared the durable queue; a process without the in-memory authorization context claimed the retry and failed at stage 1 with `ARCHIVE_RUNTIME_CONTEXT_UNAVAILABLE`. Third, unified export reused the ordinary 30-second request timeout although it generates Word, copies a roughly 660 MB RAR, and runs HashMyFiles, so Axios degraded the failure to the generic workbench request message.
- Feedback: disc-only draft updates now atomically advance attempt and binding evidence and the manifest uses the latest valid disc number; non-disc edits remain rejected. Coordinators only claim tasks with process-local contexts. Unified export now has a dedicated 30-minute client timeout and stable messages for authorization, path, archive-result, and lifecycle failures. Publication persistence errors retain their real blocker code instead of being reported as corrupt RAR parts.

## Compatibility and safety

- Historical snapshot records, recovery, and ownership-checked cleanup remain supported.
- New direct-source attempts persist no snapshot locator or false `sealed` status.
- Successful and failed attempts leave the external source directory untouched.
- The metadata gate detects path, size, and modification-time changes. An equal-size rewrite with the original mtime restored remains an explicitly documented limitation.

## Verification

- Backend affected regression: `73 passed, 2 warnings`.
- Frontend affected regression: `2 files, 19 passed`; jsdom/Ant Design emitted existing non-fatal warnings.
- Real WinRAR integration: passed; listing and extraction have exactly one top-level directory equal to the source basename, with no `.i`, `.inputs`, `.t`, snapshot, copying, or absolute staging path.
- `lint:arch` and `typecheck`: passed.
- Mutation effectiveness: temporarily removing the post-WinRAR metadata verification made the source-change test fail; restoring it made the test pass.
- First scoped Level 3 gate passed preflight, architecture, type, governance, asset, and all 279 frontend tests. Backend reported `960 passed, 3 skipped, 2 failed`: one long-path fixture boundary was exactly 120 rather than greater than 120, and one source-mutation test used an equal-size rewrite that could retain the same filesystem timestamp. Both test fixtures were made deterministic before the final rerun.
- Final scoped Level 3 gate: PASS. `preflight`, `lint:arch`, `typecheck`, `test:governance`, `check:repository-assets`, full `test`, `build`, and `verify:docs:strict` all passed using a repository-external D-drive temporary root; that temporary directory was removed afterward.
- UI manual acceptance: N/A because the confirmation, cancellation, deferred/interrupted entry points, and queued/archiving warnings are covered by RTL tests.
- Follow-up backend affected regression after manual acceptance fixes: `125 passed, 4 warnings`; the warnings are the existing synthetic configured-root warning.
- Follow-up frontend affected regression: `3 files, 33 passed`; existing jsdom/Ant Design warnings remained non-fatal.
- `lint:arch` and `typecheck` passed after the follow-up changes.
- Manual evidence: the third archive attempt succeeded. The failed export click created no unified-export audit event or formal Word artifact, so successful end-to-end export remains to be rechecked after restarting a single updated backend instance.
- First follow-up independent review: REJECT. It identified a disc-update TOCTOU between Manifest assembly and publish-intent creation, plus orphan queued-task starvation after a context-owning process exits.
- Remediation adds CAS-bound publication snapshots with bounded Manifest rebuild, internal context-binding leases that do not alter task revision, graceful queued-task interruption, never-leased-task recovery, and expired-lease recovery by another coordinator. The focused remediation regression passed `104 tests` with 5 existing synthetic-root warnings; architecture lint and typecheck passed. Focused lease edge tests passed 7 cases and architecture lint passed after extracting the lease repository below the 400-line limit.
- Third follow-up independent review after explicit human authorization: PASS with no MUST FIX. The reviewer confirmed task revision isolation, atomic claim/lease clearing, initial/never-leased/expired/graceful-stop convergence, lease renewal race closure, and the publication CAS boundary.
- Final broad affected backend regression: `130 passed, 4 warnings`.
- First final scoped gate: frontend `279 passed`; backend `969 passed, 3 skipped, 1 failed` because a legacy long-path fixture assumed at least 120 available relative characters under every temp-root prefix. The fixture now asserts a meaningful positive nested segment while retaining the actual `<260`/`>=260`, `.i/`, snapshot resolution, source-tree, and content checks; isolated same-temp-root rerun and independent assertion review passed.
- Final scoped Level 3 gate rerun: PASS. `preflight`, `lint:arch`, `typecheck`, `test:governance`, `check:repository-assets`, full `test`, `build`, and `verify:docs:strict` all passed using the repository-external D-drive temporary root.

## Review handling

- First independent review: REJECT. It found false `sealed` snapshot persistence for new attempts and insufficient real-RAR root assertions.
- Both blockers were fixed with persistence and real WinRAR extraction evidence.
- Second independent review: PASS with no MUST FIX.
- Non-blocking follow-up: if error reporting is refined later, preserve cancellation, ownership-loss, and unsafe-process-termination diagnoses rather than always prioritizing a simultaneous metadata change.

## Boundary retained for later work

- This iteration does not remove legacy snapshot schema or cleanup code because existing attempts may still reference it.
- The active OpenSpec change is not archived in this implementation turn.
