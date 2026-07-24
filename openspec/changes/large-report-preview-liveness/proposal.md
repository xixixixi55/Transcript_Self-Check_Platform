# Proposal: Large Report Preview Liveness

> Change ID: `large-report-preview-liveness`
> Status: `PROPOSED`
> Level: 3
> Date: 2026-07-24
> Baseline: `master` / `origin/master` synchronized; repository clean

## Why

Folder-mode preview currently performs three independent heavyweight operations before returning the editable report:

1. Parser dependency discovery and content fingerprinting enumerate and read the same device JSON files that the Parser later opens again.
2. Each device Parser repeats the device-directory lookup and reopens overlapping JSON files instead of consuming one request-local input snapshot.
3. The Controller synchronously creates a full `ArchiveContext` and metadata inventory before returning the preview.

Runtime measurement on a real, out-of-repository multi-material vendor report found 3 parsed material/device records and 141,209 files. The complete synchronous path took about 533 seconds: dependency fingerprinting about 118 seconds, device parsing about 299 seconds, and ArchiveContext inventory about 115 seconds. A frontend timeout increase would only hide the duplicate work and would leave retries unsafe.

The preview contract must therefore end after authorized parsing and cache persistence. Full archive inventory and archive evidence preparation belong to the explicit archive-preparation action that follows user confirmation.

## Goals

- Return a Legacy-compatible `InspectionReport` preview without waiting for full-report inventory.
- Build a request-scoped, controlled parser input snapshot that reuses core JSON, format detection, device rows, directory indexes, and parsed dependency metadata.
- Make the first parse read and digest each actual dependency in one controlled pass.
- Make cache hits validate dependency metadata first and recalculate content digests only for changed dependencies.
- Join same-directory in-flight requests before dependency discovery, fingerprinting, Parser execution, and cache persistence.
- Return an explicit archive-not-prepared state; never use `idle` to imply that a full ArchiveContext exists.
- Materialize a full ArchiveContext only after an explicit archive-preparation action, preserving all formal archive safety gates.
- Allow an explicit report-only Word export after preview without requiring archive preparation; keep Manifest-bound formal archive export fully gated.
- Make the preview UI passive with respect to WinRAR and give archive preparation its own state and loading lifecycle.

## Non-Goals

- Do not enter Shadow or Canonical implementation, comparison, routing, or output changes.
- Do not change the formal WinRAR planner, executor, RAR/Manifest integrity rules, Word template, or Legacy DTO shape.
- Do not solve the problem by increasing the frontend 120-second timeout.
- Do not add real case paths, case names, personnel/device identifiers, real reports, generated output, or large binary fixtures to the repository.

## Capabilities

### CAP-PREVIEW-SNAPSHOT-001: Request-scoped parser input snapshot

Core public JSON, format detection, device rows, evidence-directory resolution, and the actual Parser dependency set are loaded once per parse task and reused by all downstream Parser stages.

### CAP-PREVIEW-CACHE-002: Dependency-aware parse cache

The cache records only actual Parser dependencies. First-parse digest work is combined with parsing; cache hits perform metadata-first validation and only rehash dependencies whose identity metadata changed. Unrelated media, attachment HTML, and non-business JSON do not invalidate the business parse cache.

### CAP-PREVIEW-INFLIGHT-003: Same-directory in-flight reuse

All requests for the same normalized report directory join one bounded, expiring in-flight task before any expensive filesystem work. A client Abort cancels only that request's waiter and cannot create a second parse task.

### CAP-ARCHIVE-LIFECYCLE-004: Preview and full ArchiveContext separation

Preview returns an explicit not-prepared archive state and, if needed, an opaque short-lived authorized context shell. Full inventory is created only by the later archive-preparation action and remains the sole input to formal archive execution.

### CAP-FRONTEND-LIVENESS-005: Passive preview and independent archive preparation state

Loading, errors, retry, and archive-preparation status are independent. Preview success does not start WinRAR; an archive context that is not prepared is represented accurately and cannot be consumed as a ready context.

## Impact

| Layer | Impact | Expected scope |
|---|---|---|
| Layer 0 SharedTypes | Add explicit preview/archive-readiness status and optional shell summary fields while preserving `InspectionReport`, `ArchiveManifest`, and Legacy DTO fields | `packages/shared/types/archive.ts`, `packages/shared/types/index.ts` |
| Layer 1 Constants | Add only the generic archive-preparation endpoint/status constants required by this lifecycle change | `packages/shared/constants/index.ts` |
| Layer 2 SharedUtils | No mandatory change; add pure normalization helpers only if shared contract validation requires them | Existing shared utils, only if justified |
| Layers 10-12 Frontend | Stop automatic archive preparation, display explicit not-prepared state, isolate archive-preparation loading/errors, allow report-only Word export, and keep Manifest-bound formal export gated | `useReportParser.ts`, `useArchivePreparation.ts`, archive status UI, `RecordGeneratePage.tsx` |
| Layer 20 Backend Repository | Controlled input snapshot, dependency index, per-file metadata/digest reuse, and path-free identity handling | New snapshot/digest repository modules plus existing identity helpers |
| Layer 21 Backend Services | Parser orchestration, cache integration, in-flight registry, context shell, and full-context materialization | `report_parser_service.py`, cache/runtime services, new lifecycle services |
| Layer 22 Backend Controllers | Preview response assembly without full inventory and explicit archive-preparation boundary | `record_controller.py`, `archive_controller.py` |
| Layer 23 Routes | Register only the generic preparation route if design review confirms it is required | Existing route registration |

### Public contract strategy

The parsed `InspectionReport`, `rar_info` compatibility field, and formal `ArchiveManifest` remain unchanged. The parse response gains an explicit archive-readiness field and may return an opaque context-shell identifier. A shell is not a full inventory and is not formal archive evidence. Existing consumers that only read the report continue to work. A report-only Word export may consume the editable report without a shell or Manifest; any archive execution or Manifest-bound formal export must reject a non-ready shell with a stable, actionable state.

The generic preparation boundary accepts only the authorized report-directory source record.

## Level 3 rationale

This change modifies a core data-conversion pipeline, persistent cache identity, request concurrency semantics, the preview response lifecycle, and the security boundary between an authorized source and a formal ArchiveContext. It may change shared API types and introduces a new lifecycle boundary used by explicit archive preparation. It therefore requires proposal, spec, design, tasks, implementation, verification, independent review, manual real-report acceptance, and archive in the Level 3 workflow.

## Acceptance summary

- First preview of a representative multi-material report is below 90 seconds with margin; cache-hit preview is below 15 seconds.
- Preview does not enumerate the complete report inventory or create a full ArchiveContext.
- Core JSON is parsed once per task; each dependency is read/digested once on a cache miss; cache hits do not reread unchanged dependency contents.
- Same-directory concurrent requests share one task, including after a client timeout.
- Legacy and New report DTOs remain equivalent to the pre-change parser for supported fixtures.
- Explicit archive preparation performs complete inventory, readability, path/link, change, full-content-fingerprint, WinRAR, Manifest, and RAR validation before formal output.
- Report-only Word export remains available when archive preparation is not requested; it does not claim a validated archive or Manifest.
