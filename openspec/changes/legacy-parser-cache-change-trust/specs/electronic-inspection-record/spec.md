## MODIFIED Requirements

### Requirement: REQ-011: 解析缓存

The system SHALL cache the complete Legacy parse result (`InspectionReport` plus compatibility `rar_info`) under an opaque key in `output/parsed/`. A cache record SHALL contain the source content fingerprint, `cache_version`, `input_trust_schema`, and `last_accessed_at`, and MUST NOT contain an absolute path for frontend display. The existing parser semantic `cache_version` remains `7`; the independent `input_trust_schema` identifies whether the source-change trust contract has been applied. At most five valid parse cache records SHALL be retained using deterministic LRU eviction. Parse-cache cleanup MUST remain separate from archive output cleanup.

#### Scenario: First parse creates a versioned cache record

- **WHEN** a report directory is parsed successfully
- **THEN** the system stores the complete Legacy parse result as an opaque JSON cache record
- **AND** the record contains the source fingerprint, `cache_version`, `input_trust_schema`, and `last_accessed_at`
- **AND** the record contains no absolute source path for frontend display
- **AND** parsing does not execute WinRAR or create a final `ArchiveManifest`

#### Scenario: Unchanged report reuses a trusted cache

- **WHEN** the same normalized report directory is parsed again with the same parser cache version
- **AND** the selected dependency membership is unchanged
- **AND** every dependency is confirmed `trusted_unchanged` by the unified file-change contract
- **THEN** the system returns the cached Legacy `InspectionReport` without rereading all dependency contents or rerunning parsing
- **AND** it updates `last_accessed_at` without creating a duplicate cache record
- **AND** it does not execute or reuse WinRAR results

#### Scenario: Changed report invalidates the cache

- **WHEN** a dependency is overwritten in place, atomically replaced, deleted and recreated, added, deleted, or otherwise changes its content or identity
- **THEN** the cache MUST be invalidated or completely revalidated
- **AND** the system MUST rebuild the `InspectionReport` when the new input is readable
- **AND** the old `InspectionReport` MUST NOT be returned

#### Scenario: Untrusted source does not produce a false cache hit

- **WHEN** the source is non-NTFS, network/mobile/cloud-backed, permission-restricted, the Journal is rebuilt or unverifiable, the API fails, or verification cannot prove that content is unchanged
- **THEN** the system MUST completely read and digest the required dependencies before reusing a cache record
- **AND** a failed or changing read MUST fail parsing rather than return the old cache

#### Scenario: Old cache record is safely upgraded

- **WHEN** a valid old cache record lacks `input_trust_schema` or uses an older input-trust schema
- **THEN** the system MUST perform complete content verification before reuse
- **AND** it MAY rewrite the record using the current input-trust schema after successful verification
- **AND** a corrupt, incomplete, or invalid record MUST be treated as a cache miss

#### Scenario: LRU eviction remains isolated

- **WHEN** a sixth valid parse cache is created
- **THEN** the record with the oldest deterministic `last_accessed_at` is removed
- **AND** eviction MUST remove only parse cache records under `output/parsed/`
- **AND** eviction MUST NOT delete RAR, `ArchiveManifest`, archive downloads, Word exports, source reports, defaults, or other outputs

#### Scenario: User clears parser cache

- **WHEN** the user confirms the stage-one clear-parser-cache action
- **THEN** the parser cache endpoint returns a clear result and the next parse rereads the source inputs
- **AND** already loaded frontend report data does not need to disappear immediately
- **AND** clearing parser cache MUST NOT delete RAR, `ArchiveManifest`, archive downloads, Word exports, source reports, defaults, or other outputs
