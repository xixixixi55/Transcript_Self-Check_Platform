## ADDED Requirements

### Requirement: Unified file-change trust state

The parser SHALL evaluate every dependency through one internal file-change trust contract. The contract MUST distinguish `trusted_unchanged`, `changed`, and `untrusted`; only `trusted_unchanged` permits reuse of a stored digest. The public API, user-facing errors, and logs MUST expose only opaque identifiers and reason codes, never absolute paths.

#### Scenario: Trusted NTFS file is reused without content reread

- **WHEN** the source is a supported local NTFS file, the current volume and Journal identity are valid, the file identity and per-file USN token equal the stored token, and the directory membership is unchanged
- **THEN** the system reuses the stored digest without rereading that file's content
- **AND** the parser cache may reuse the corresponding `InspectionReport`

#### Scenario: Same-stat content replacement is detected

- **WHEN** a file is overwritten in place with different content while its path, size, stat timestamps, and file identity remain unchanged
- **THEN** the current per-file change token MUST differ or the provider MUST return `untrusted`
- **AND** the old digest and old `InspectionReport` MUST NOT be returned

#### Scenario: Unsupported or uncertain source uses safe fallback

- **WHEN** the source is non-NTFS, a network/mobile/cloud source, permission-restricted, missing, or the USN/API/Journal state cannot prove unchanged content
- **THEN** the system MUST perform a complete content digest verification for the affected dependencies
- **AND** a successful fallback MUST still allow normal parsing
- **AND** a failed fallback MUST fail parsing rather than return the old cache

### Requirement: Directory membership trust

The system SHALL validate the sorted relative-path and entry-type membership of every candidate directory and selected dependency set. A membership change MUST invalidate the parser cache without requiring a full content read of unrelated files.

#### Scenario: Dependency file is added or removed

- **WHEN** a selected dependency is added, deleted, or becomes unreadable
- **THEN** the cached input MUST be marked changed or untrusted
- **AND** the old parse result MUST NOT be returned

#### Scenario: Dependency file is atomically replaced or recreated

- **WHEN** a selected path is replaced by another file or deleted and recreated
- **THEN** the system MUST compare file identity and change token
- **AND** it MUST invalidate or safely revalidate the cache before parsing

### Requirement: Read consistency and TOCTOU handling

The system SHALL verify file state before and after content reads. It MUST NOT publish a digest, cache record, or parse result when the file identity, size, or change token differs across the read.

#### Scenario: File changes during content verification

- **WHEN** a dependency changes while its bytes are being read
- **THEN** the system MUST discard the candidate digest and cached result
- **AND** it MUST return an input-changed or equivalent retryable parse failure
- **AND** it MUST NOT use sleep, random retry, or a stale result to hide the race

#### Scenario: Verification state cannot be confirmed before reuse

- **WHEN** the provider cannot complete the final token confirmation before a cache hit is returned
- **THEN** the system MUST use complete content verification instead of returning the cached result

### Requirement: Process and restart trust boundaries

The system SHALL distinguish process-local digest memoization from disk-persisted parsed results. Process-local tokens MUST NOT be assumed after restart. A disk cache record without the current input-trust schema MUST require complete content verification before reuse.

#### Scenario: Service restarts before a cache hit

- **WHEN** the service restarts and a disk parser cache record exists without a verifiable current-process token
- **THEN** the first reuse attempt MUST perform complete content verification
- **AND** only a successful verification may establish new process-local trust

#### Scenario: Legacy cache record is migrated

- **WHEN** a syntactically valid old cache record lacks `input_trust_schema`
- **THEN** the system MUST verify all required input content before reuse
- **AND** it MAY rewrite the record with the current schema after successful verification
- **AND** a malformed or invalid record MUST be treated as a cache miss

### Requirement: Packaged Windows behavior

The change-token adapter SHALL be lazily loaded in the backend and SHALL not require the customer to install an additional system component. The final packaged executable MUST preserve safe fallback behavior when Win32 calls fail.

#### Scenario: Packaged executable cannot access USN

- **WHEN** the packaged executable runs under a supported account but the USN call returns an access or API error
- **THEN** the parser MUST continue using complete content verification
- **AND** diagnostics MUST use an opaque reason code without exposing the source path
