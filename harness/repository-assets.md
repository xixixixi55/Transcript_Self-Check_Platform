# Repository Asset Policy

## Canonical Production Assets

### Word Template

| Asset | Status |
|-------|--------|
| `word_templates/template.docx` | **Tracked — do not modify casually** |

- This is the single authoritative Word report template.
- Identity verified by OOXML package fingerprint (SHA-256 of canonical blob).
- Must never be rewritten by a generation run.
- Any modification requires independent acceptance testing.

## Test Fixtures

All test data must be **explicitly synthetic**:

- Use markers: `SYNTHETIC`, `TEST`, `FIXTURE`, or `脱敏示例`.
- Never copy-paste from a real case report.
- Never include real names, case numbers, file paths, or device identifiers.
- Binary fixtures must document their purpose and generation method.

If a fixture value *looks* real but you cannot confirm its origin, treat it as sensitive.

## Locally Generated Assets

These directories must **never** be tracked in Git:

- `output/`
- `packages/output/`
- Any nested `output/` directory

Generated files that stay local-only:

- Exported DOCX
- Parsed JSON/TXT
- Archive volumes (`.rar`, `.zip`)
- Acceptance screenshots and checklists

## Reference Assets

Reference templates, client-supplied samples, and historical versions:

- Default: **do not enter Git**.
- Must be safety-reviewed before any exception.
- Store in controlled local or private-asset locations when needed.
- Never mix reference assets with the canonical production template.

## Sensitive Data — Never Commit

- Real case names, numbers, or identifiers
- Real person names or unit names
- Device serial numbers, IMEI, or hardware identifiers
- Local user paths or workstation names
- Parsed report data
- Archive hashes or disc numbers
- Business-generated documents containing any of the above

## Post History-Rewrite Collaboration Rules

1. **All collaborators must re-clone** from the rewritten remote.
2. **Never push from an old clone** — it carries the old, sensitive history.
3. **Never merge old branches** into the rewritten history.
4. Old backup bundles and mirrors contain sensitive data — store securely, destroy when no longer needed.

## Hygiene Check

Run before committing:

```bash
npx tsx scripts/check-repository-assets.ts
```

This gate is also wired into `pnpm verify:quick`.
