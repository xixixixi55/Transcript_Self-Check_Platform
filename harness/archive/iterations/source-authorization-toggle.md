# Iteration: source authorization toggle

- Date: 2026-08-04
- Change: `openspec/changes/extensible-report-template-platform`
- Scope: homepage-only persisted source authorization mode, arbitrary local report-directory registration, retained path/output/report safety checks, and removal of the old authorization notice/readiness item.

## Problem → cause → feedback

- Problem: the configured source-root authorization explanation had become a redundant user-facing gate even though users already know the local folder they intend to register.
- Cause: the original authorization boundary was applied unconditionally at source registration, while the browser had no ordinary-user preference for temporarily disabling that boundary.
- Feedback: the browser now stores `biji.sourceAuthorization.enabled`, defaults new profiles to `false`, and sends the current mode on workbench submission and source replacement. Backend/API defaults remain `true` for direct callers; disabled mode skips only configured-root/exact-grant authorization and keeps path, reparse, output-overlap, and report-structure checks. The legacy directory-parse request contract also has a shared mode field and a frontend request builder; no active frontend route currently calls the deprecated endpoint directly.

## Verification

- Backend affected tests: `98 passed, 2 warnings`.
- Frontend affected tests: `7 files, 22 passed`.
- `lint:arch` and `typecheck`: passed.
- Mutation effectiveness: temporarily disabling the repository's `source_authorization_enabled=false` branch caused both disabled-mode tests to fail; restoring the branch made both pass.
- `git diff --check`: passed; Git line-ending normalization warnings only.

## Review handling

- First independent review returned REJECT with findings about legacy request propagation, shared request types, and missing mode-matrix assertions.
- The findings were addressed in this candidate. Per the user's instruction, no second review was started; final confidence is based on the added shared contract, targeted tests, mutation check, and final automated gates.

## Boundary retained for later work

- The existing `extensible-report-template-platform` change package remains active because unrelated canonical/archive/manual-acceptance tasks are still pending; this iteration does not archive or commit the package.
- Browser localStorage is a user-profile preference, not administrator configuration. Direct API callers that omit the field retain the existing strict default.
