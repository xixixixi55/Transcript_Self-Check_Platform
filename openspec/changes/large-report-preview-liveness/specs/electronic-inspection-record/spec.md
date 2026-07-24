# Spec: Large Report Preview Liveness

> Baseline Spec: `openspec/specs/electronic-inspection-record/spec.md`
> Change: `large-report-preview-liveness`
> Status: `PROPOSED`; this document describes intended behavior and is not current production behavior.

## CAP-PREVIEW-SNAPSHOT: Preview uses one controlled parse task

### REQ-PREVIEW-SNAPSHOT-001: Folder preview ends after parsing

The folder-mode preview request MUST authorize the selected directory, parse the supported report, persist the parse result, and return the editable preview without creating a full ArchiveContext or scanning the complete report inventory.

**Scenario: Multi-material folder preview succeeds**

- WHEN a user selects an authorized, supported Legacy or New report directory
- THEN the backend returns a Legacy-compatible `InspectionReport` after parser cache persistence
- AND the response does not wait for full input inventory, WinRAR execution, Manifest creation, or RAR validation
- AND the response reports archive readiness as `not_prepared` or an equivalent explicit state
- AND no field named `idle` is used to imply that a full ArchiveContext is ready

**Scenario: Authorization or format validation fails**

- WHEN the selected directory is outside the authorized scope, overlaps an output root, contains a forbidden link/reparse point, or has unsupported core structure
- THEN the request fails before parser work or context-shell publication
- AND the response contains a stable safe error without a local path, case data, or stack trace

### REQ-PREVIEW-SNAPSHOT-002: Request-scoped core input reuse

Within one parse task, the system MUST load and parse each core public JSON once, reuse the detected format and device rows, and reuse the evidence-directory index across dependency discovery, DTO construction, and cache persistence.

**Scenario: Core JSON is reused**

- WHEN a supported report is parsed
- THEN `data_case_info.json`, `data_device_lists.json`, and `data_report_info.json` are not independently reloaded by format detection, dependency discovery, and DTO assembly
- AND all consumers use the same request-scoped values

**Scenario: Multiple material records are parsed**

- WHEN a report contains multiple device/material rows
- THEN directory resolution and parser metadata are reused per evidence number
- AND one material parser cannot trigger a fresh scan of the report root for every other material

### REQ-PREVIEW-SNAPSHOT-003: Controlled dependency discovery

The Parser MUST dynamically register the files it actually reads for business fields. It MUST NOT pre-read media, attachment HTML, navigation payloads, or unrelated JSON merely to calculate a parse-cache fingerprint.

**Scenario: Parser reads a relevant dependency**

- WHEN a device field is extracted from a JSON file
- THEN that file is recorded with normalized relative path, size, modification time, and content digest during the same read
- AND the dependency record is internal and contains no absolute path in public output or persistent cache keys

**Scenario: Unrelated source content changes**

- WHEN a media file, attachment HTML, or JSON not used by the business Parser changes
- THEN the business parse cache remains eligible for reuse
- AND the preview DTO remains unchanged unless an actual Parser dependency changed

### REQ-PREVIEW-SNAPSHOT-004: DTO compatibility

The optimized parser MUST preserve the existing Legacy DTO values and supported New DTO values for the same source inputs, including evidence ordering, device identifiers, software fields, `rar_info` compatibility semantics, and editable report defaults.

**Scenario: Legacy process and result include every material**

- WHEN a Legacy report contains multiple ordered evidence/material records
- THEN the existing scalar `inspection.result.evidence_number` field contains the ordered material numbers joined with `、`
- AND the existing `inspection.process_steps` strings mention every material number in the same order
- AND the DTO shape and single-material wording remain compatible

**Scenario: Device display name uses the effective model**

- WHEN a Legacy or New report provides a generic device name and a concrete model
- THEN `evidence_list[].device_name` uses the normalized brand/model display value
- AND `evidence_list[].model` preserves the concrete model value
- AND `evidence_list[].device_type` remains the explicit report type instead of the generic display name

**Scenario: Legacy fixture parity**

- WHEN the optimized parser and the pre-change parser process the same synthetic Legacy fixture
- THEN their normalized `InspectionReport` values are equal except for explicitly documented cache/readiness metadata
- AND no path, digest, or internal snapshot field appears in the report DTO

**Scenario: New fixture parity**

- WHEN the optimized parser processes a supported synthetic New fixture
- THEN it preserves the existing New-format field mapping and does not route the report through a Legacy-only fallback that changes the DTO

## CAP-PARSE-CACHE: Dependency-aware cache identity

### REQ-PARSE-CACHE-001: One-pass first parse

On a cache miss, parsing and dependency digest registration MUST happen in one controlled read pass. The implementation MUST NOT first fully content-fingerprint the dependency set and then reopen the same files for the Parser.

**Scenario: Cache miss**

- WHEN no valid parse cache exists for a normalized report directory
- THEN the parser reads each actual dependency, extracts the needed fields, and records its path metadata and digest in the same pass
- AND the cache write contains the dependency manifest needed for later validation

### REQ-PARSE-CACHE-002: Metadata-first cache hit

On a cache lookup, the system MUST validate dependency paths, sizes, modification times, and stable file identity metadata before opening file contents. Unchanged dependencies reuse stored digests; only changed or newly discovered dependencies are rehashed.

**Scenario: Cache hit with unchanged dependencies**

- WHEN all recorded dependency paths exist with unchanged identity metadata and the cache version is current
- THEN the system returns the cached report without reopening dependency contents
- AND it updates last-access metadata without creating a duplicate cache entry

**Scenario: One dependency changes**

- WHEN a recorded dependency is added, removed, resized, or has changed modification/identity metadata
- THEN only the affected dependency set is rehashed before deciding cache validity
- AND an actual content change causes a fresh parse and cache replacement

**Scenario: Cache is damaged or stale**

- WHEN a cache file is malformed, its version is obsolete, its dependency manifest is incomplete, or its build failed before publication
- THEN the record is ignored and cleaned according to existing cache lifecycle rules
- AND no partial report or permanent in-flight entry is returned

### REQ-PARSE-CACHE-003: Cache scope isolation

The parse cache MUST remain independent of original report directories, ArchiveContext inventory, RAR files, ArchiveManifest records, Word exports, Shadow state, and Canonical state.

**Scenario: Parse cache is cleared**

- WHEN the user clears report parse cache
- THEN only parse-cache records are removed
- AND no source handle, formal archive, Manifest, Word export, or user-provided source file is deleted or invalidated by path traversal

## CAP-PARSE-INFLIGHT: Same-directory request reuse

### REQ-PARSE-INFLIGHT-001: Join before expensive work

The in-flight registry MUST be keyed by the normalized opaque report-directory identity and MUST be acquired before dependency discovery, content fingerprinting, Parser execution, or parse-cache persistence.

**Scenario: Concurrent same-directory requests**

- WHEN two or more requests arrive for the same normalized report directory
- THEN one bounded task performs the expensive parse pipeline
- AND later requests join that task and receive the same successful result or the same safe failure
- AND the Parser and cache writer execute once for the shared task

**Scenario: Distinct directories**

- WHEN requests target different normalized report directories
- THEN they do not share results or dependency manifests
- AND the registry enforces a configured capacity so unrelated reports cannot exhaust memory or worker capacity

### REQ-PARSE-INFLIGHT-002: Abort and failure lifecycle

Client cancellation MUST detach only the cancelled waiter from the shared task. It MUST NOT start a duplicate task for a retry while the first task is still running.

**Scenario: Frontend Abort followed by retry**

- WHEN the first request reaches the frontend timeout or network cancellation and a user retries the same directory
- THEN the retry joins the existing in-flight task or consumes its completed cache result
- AND no second dependency discovery, Parser run, or cache write starts for that directory

**Scenario: Shared task fails**

- WHEN the shared Parser task fails or is cancelled by a server-side lifecycle policy
- THEN all current waiters receive a safe retryable error
- AND the registry removes the failed entry after publishing the result
- AND a later retry can start a fresh task

### REQ-PARSE-INFLIGHT-003: Bounded lifecycle and safe observability

In-flight entries MUST have capacity, creation/last-observed timestamps, explicit completion state, and exception cleanup. Logs and metrics MUST use opaque keys or counters and MUST NOT include absolute paths, case data, or cache contents.

## CAP-ARCHIVE-LIFECYCLE: Full inventory is explicit and deferred

### REQ-ARCHIVE-LIFECYCLE-001: Preview returns not-prepared state

Preview MAY publish a short-lived authorized context shell, but it MUST NOT publish it as a full inventory-bearing ArchiveContext. The response MUST distinguish `not_prepared`, `preparing`, `ready`, and `failed` states.

**Scenario: Preview returns a context shell**

- WHEN folder parsing succeeds and a later archive action needs a stable source reference
- THEN the backend may return an opaque shell identifier bound to the authorization and short TTL
- AND the shell has no full file count, total input size, or formal inventory claim
- AND a shell cannot be used by formal archive execution or Manifest-bound formal export until materialized and validated

**Scenario: Preview response is consumed by an old report-only client**

- WHEN a client only reads `report`, `parsed_files`, or compatibility `rar_info`
- THEN it continues to function without requiring a ready ArchiveContext
- AND clients that need archive execution receive a stable not-prepared error rather than a misleading `idle` success

### REQ-ARCHIVE-LIFECYCLE-002: Explicit preparation materializes full context

The archive-preparation action MUST be separate from preview. It MUST resolve the authorized shell/source, build the complete inventory, and publish a ready ArchiveContext only after the inventory is complete.

**Scenario: User explicitly starts archive preparation**

- WHEN the user explicitly starts archive preparation after preview
- THEN the system creates or refreshes the full ArchiveContext and reports independent preparation loading/status
- AND preview completion alone never starts WinRAR or full inventory

**Scenario: Preparation is repeated**

- WHEN an existing shell or context is prepared again for the same authorized source
- THEN the runtime applies bounded snapshot reuse where safe, but never skips required currentness checks
- AND the resulting context status accurately reports whether full inventory is ready

### REQ-ARCHIVE-LIFECYCLE-003: Formal archive gates remain complete

Moving inventory out of preview MUST NOT weaken formal archive safety. Before WinRAR execution or formal archive validation, the system MUST retain complete inventory, readability, path-boundary, link/reparse, add/remove/change, full input-content fingerprint, Manifest, RAR, and download/export checks required by the current archive contract.

**Scenario: Source changes after preview**

- WHEN a file is added, removed, modified, unreadable, or replaced by a link/reparse point after preview but before archive preparation/execution
- THEN preparation or formal execution fails with a safe input-changed/path error
- AND preview cache or shell metadata is not treated as formal archive evidence

**Scenario: Archive preparation fails**

- WHEN full inventory or a formal archive gate fails
- THEN the context status becomes `failed` with a retryable safe error
- AND no partial Manifest is published and no user-owned source is deleted

## CAP-FRONTEND-LIVENESS: Preview and archive preparation are independent

### REQ-FRONTEND-LIVENESS-001: Preview does not auto-archive

The preview UI MUST not call archive execution as a side effect of report load, a valid disc number, or ordinary report editing.

**Scenario: Report enters review**

- WHEN parsing succeeds and the review page opens
- THEN the page displays the report preview and an explicit archive-not-prepared state
- AND it does not start a WinRAR request, archive polling loop, or full inventory request

**Scenario: User edits ordinary fields**

- WHEN the user edits report fields, disc metadata, or photos before selecting an archive action
- THEN only local review state changes
- AND no archive preparation request starts automatically

### REQ-FRONTEND-LIVENESS-002: Loading and retry cleanup

Preview and archive preparation MUST have separate loading, error, cancellation, and retry state. Every success, business error, service error, network failure, timeout, and cancellation MUST end the corresponding loading state.

**Scenario: Preview timeout or network failure**

- WHEN preview fails, times out, or is cancelled
- THEN preview loading ends and a retryable message is shown
- AND a retry cannot create a second backend parse task for the same normalized directory

**Scenario: Archive preparation failure**

- WHEN archive preparation fails after preview success
- THEN preview data remains editable
- AND only archive-preparation state becomes failed; Manifest-bound formal export remains blocked until a validated Manifest exists

### REQ-FRONTEND-LIVENESS-003: Independent Word export and formal archive gate

The UI and Controller MUST allow an explicit report-only Word export after a successful editable preview when no archive context or Manifest is supplied. This path MUST keep the existing report-field and document-rendering validation, MUST NOT start WinRAR, and MUST NOT claim archive or Manifest evidence. When an archive context or Manifest is supplied, the operation is formal and MUST reject an unready context or unvalidated Manifest.

**Scenario: Report-only Word export before archive preparation**

- WHEN the user explicitly exports the editable report while archive status is `not_prepared`
- THEN the system generates and downloads a Word report without creating a full ArchiveContext or executing WinRAR
- AND the result does not claim a validated Manifest or formal archive evidence

**Scenario: Formal export still requires a validated Manifest**

- WHEN the export request supplies an archive context or Manifest identifier
- THEN the Controller requires a current ready context and validated Manifest before formal export
- AND a missing, partial, stale, or invalid archive contract fails with a stable safe error

## CAP-CHANGE-BOUNDARIES: Archive source and output boundaries

### REQ-CHANGE-BOUNDARIES-001: authorized report-directory source

The archive-preparation boundary MUST use the authorized report-directory source record created by preview.

**Scenario: Explicit directory-backed archive preparation**

- WHEN the user explicitly starts archive preparation after preview
- THEN the Controller resolves the authorized source record and revalidates the report directory
- AND full inventory and formal archive safety gates run before any archive or Manifest-bound export
- AND preview state, parse cache data, and source handles are not treated as formal archive evidence

### REQ-CHANGE-BOUNDARIES-002: Shadow and Canonical isolation

- WHEN this change is implemented or verified
- THEN no Shadow or Canonical parsing, comparison, route, or output behavior is added
- AND the formal Legacy DTO and Word/Manifest consumer contract remains the compatibility boundary

## CAP-ACCEPTANCE: Performance and regression targets

### REQ-ACCEPTANCE-001: Representative performance

**Scenario: Real local manual validation**

- WHEN a release candidate is manually run against the previously measured external multi-material report
- THEN first preview is below 90 seconds with reasonable margin
- AND a valid cache-hit preview is below 15 seconds
- AND preview does not create full inventory or enumerate the complete input tree
- AND the report path, case name, business content, and generated output remain outside repository assets, logs, tests, and Git

**Scenario: Synthetic automated benchmark**

- WHEN automated performance tests run
- THEN they use only small synthetic fixtures marked `SYNTHETIC`, `TEST`, or `FIXTURE`
- AND they assert read counts, dependency scope, in-flight sharing, and no full inventory during preview without requiring GB-scale files

### REQ-ACCEPTANCE-002: Formal archive regression

- WHEN the user explicitly prepares an archive after preview
- THEN current generated-archive planning, WinRAR execution, full integrity validation, Manifest assembly, download validation, and Word export gates remain green
