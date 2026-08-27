/**
 * check-contracts.ts — TS↔Python cross-language contract validator
 *
 * Compares shared TypeScript type definitions against Python Pydantic models
 * and enum definitions to detect field-level drift before it reaches production.
 *
 * Checked dimensions:
 * 1. Field presence — every TS field MUST have a Python counterpart (and vice versa)
 * 2. Required/optional — optionality markers MUST agree
 * 3. Enum values — literal union / enum member sets MUST be identical
 * 4. Error code membership — ExportGateBlockerCode MUST equal ExportGateCode values
 *
 * Usage:
 *   npx tsx scripts/check-contracts.ts
 * Exit code: 0 = aligned, 1 = drift detected
 */

import * as fs from 'node:fs'
import * as path from 'node:path'

const ROOT = path.resolve(__dirname, '..')

// ─── Contract pairs: TS source → Python source ──────────────────────────

interface ContractPair {
  label: string
  tsFile: string          // relative to ROOT
  pyFile: string          // relative to ROOT
  /** TS type names whose fields MUST match Python class fields */
  modelPairs: { tsType: string; pyClass: string; tsFields?: { name: string; required: boolean }[] }[]
  /** TS type name → Python Literal name for enum comparison */
  enumPairs: { tsType: string; pyLiteral: string }[]
}

const CANONICAL_PAIRS: ContractPair = {
  label: 'canonical',
  tsFile: 'packages/shared/types/canonical.ts',
  pyFile: 'packages/backend/app/services/canonical_models_service.py',
  modelPairs: [
    { tsType: 'FieldProvenance', pyClass: 'FieldProvenance' },
    { tsType: 'MaterialIdentifier', pyClass: 'MaterialIdentifier' },
    { tsType: 'MaterialClassification', pyClass: 'MaterialClassification' },
    { tsType: 'Material', pyClass: 'Material' },
    { tsType: 'InspectorSnapshot', pyClass: 'InspectorSnapshot' },
    { tsType: 'SoftwareTool', pyClass: 'SoftwareTool' },
    { tsType: 'PrimarySoftwareCandidate', pyClass: 'PrimarySoftwareCandidate' },
    { tsType: 'PrimarySoftware', pyClass: 'PrimarySoftware' },
    // CanonicalCaseInfo: top-level TS fields only; nested introduction fields checked via CanonicalCaseIntroduction pair
    {
      tsType: 'CanonicalCaseInfo',
      pyClass: 'CanonicalCaseInfo',
      tsFields: [
        { name: 'title', required: true },
        { name: 'document_number', required: true },
        { name: 'case_number', required: true },
        { name: 'case_name', required: true },
        { name: 'introduction', required: true },
      ],
    },
    // CanonicalCaseIntroduction: TS definition is nested inside CanonicalCaseInfo
    {
      tsType: 'CanonicalCaseIntroduction',
      pyClass: 'CanonicalCaseIntroduction',
      tsFields: [
        { name: 'entrust_unit_prefix', required: true },
        { name: 'entrust_unit', required: true },
        { name: 'entrust_persons', required: true },
        { name: 'entrust_time', required: true },
        { name: 'case_summary', required: true },
        { name: 'inspection_requirement', required: true },
        { name: 'inspection_place', required: true },
      ],
    },
    { tsType: 'CanonicalInspectionPeriod', pyClass: 'CanonicalInspectionPeriod' },
    { tsType: 'CanonicalInspectionResult', pyClass: 'CanonicalInspectionResult' },
    { tsType: 'CanonicalInspectionDetails', pyClass: 'CanonicalInspectionDetails' },
    // ProcessStep: TS is inline { step_number: number; content: string }, Python has named model
    {
      tsType: 'ProcessStep',
      pyClass: 'ProcessStep',
      tsFields: [
        { name: 'step_number', required: true },
        { name: 'content', required: true },
      ],
    },
    { tsType: 'PhotoReference', pyClass: 'PhotoReference' },
    { tsType: 'ArchiveManifestSummary', pyClass: 'ArchiveManifestSummary' },
    { tsType: 'MaterialPhotoGroup', pyClass: 'MaterialPhotoGroup' },
    // ExtractListColumn + ExtractListTable: TS is inline in CanonicalAttachmentInputs.extract_list
    {
      tsType: 'ExtractListColumn',
      pyClass: 'ExtractListColumn',
      tsFields: [
        { name: 'key', required: true },
        { name: 'title', required: true },
        { name: 'width', required: false },
      ],
    },
    {
      tsType: 'ExtractListTable',
      pyClass: 'ExtractListTable',
      tsFields: [
        { name: 'columns', required: true },
        { name: 'rows', required: true },
      ],
    },
    { tsType: 'CanonicalAttachmentInputs', pyClass: 'CanonicalAttachmentInputs' },
    { tsType: 'CanonicalInspectionCase', pyClass: 'CanonicalInspectionCase' },
  ],
  enumPairs: [
    { tsType: 'MaterialKind', pyLiteral: 'MaterialKind' },
    { tsType: 'MaterialClassificationStatus', pyLiteral: 'MaterialClassificationStatus' },
    { tsType: 'MaterialClassificationSource', pyLiteral: 'MaterialClassificationSource' },
    { tsType: 'IdentifierType', pyLiteral: 'IdentifierType' },
    { tsType: 'SoftwareCategory', pyLiteral: 'SoftwareCategory' },
    { tsType: 'ConfirmationStatus', pyLiteral: 'ConfirmationStatus' },
  ],
}

// These editable TS inputs may omit fields that the Python canonical serializer
// always materializes with an empty-string default. The asymmetry is intentional;
// all other required/optional mismatches remain contract drift.
const OPTIONALITY_EXCEPTIONS = new Set([
  'Material.unextractable_reason',
  'InspectorSnapshot.position',
])

// ─── Drift reporting ────────────────────────────────────────────────────

interface Drift {
  contract: string
  dimension: 'field-name' | 'optionality' | 'enum-values' | 'error-code-set'
  detail: string
}

const drifts: Drift[] = []

function drift(contract: string, dimension: Drift['dimension'], detail: string) {
  drifts.push({ contract, dimension, detail })
}

// ─── TS parser — regex-based structural extraction ─────────────────────

interface TsField {
  name: string
  required: boolean   // false when suffixed with ?
  typeHint: string    // raw type annotation (trimmed)
}

interface TsTypeInfo {
  name: string
  kind: 'interface' | 'type' | 'enum'
  fields: TsField[]             // for interface
  unionMembers: Set<string>     // for type (literal union)
}

function parseTsSource(content: string): TsTypeInfo[] {
  const results: TsTypeInfo[] = []
  const normalized = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n')

  // Interfaces: match from "export interface Name {" to matching "}" (balanced)
  const ifaceRe = /export\s+interface\s+(\w+)\s*\{/gs
  for (const m of normalized.matchAll(ifaceRe)) {
    const name = m[1]
    const startIdx = m.index! + m[0].length
    // Find matching closing brace
    let depth = 1
    let endIdx = startIdx
    for (let i = startIdx; i < normalized.length && depth > 0; i++) {
      if (normalized[i] === '{') depth++
      else if (normalized[i] === '}') depth--
      if (depth === 0) endIdx = i
    }
    const body = normalized.slice(startIdx, endIdx)
    const fields: TsField[] = []
    // Match field lines: name?: type; or name: type;
    const fieldRe = /^\s*(?:\/\*\*.*?\*\/\s*)?(\w+)(\?)?:\s*(.+?)\s*;?\s*$/gm
    for (const fm of body.matchAll(fieldRe)) {
      fields.push({
        name: fm[1],
        required: !fm[2],
        typeHint: fm[3].trim().replace(/\s+import\(.*?\)$/, '').trim(),
      })
    }
    results.push({ name, kind: 'interface', fields, unionMembers: new Set() })
  }

  // Type aliases (literal unions): handles both single and multi-line forms.
  // Parsed line-by-line: starts at "export type Name =", ends before next "export" or blank-line+non-indented.
  const typeStartRe = /export\s+type\s+(\w+)\s*=\s*(.*)/g
  for (const ms of normalized.matchAll(typeStartRe)) {
    const name = ms[1]
    if (results.some(r => r.name === name)) continue  // skip if already captured
    const firstLine = ms[2]
    // Collect continuation lines (starting with whitespace and |)
    const startLineNum = normalized.slice(0, ms.index).split('\n').length
    const allLines = normalized.split('\n')
    let body = firstLine
    for (let j = startLineNum; j < allLines.length; j++) {
      const nextLine = allLines[j].trim()
      // Stop at next export, comment, blank line followed by non-continuation, or non-whitespace-starting
      if (!nextLine) {
        // blank line: check if next non-blank line starts with export or class
        let peek = j + 1
        while (peek < allLines.length && !allLines[peek].trim()) peek++
        if (peek < allLines.length) {
          const peekTrimmed = allLines[peek].trim()
          if (peekTrimmed.startsWith('export ') || peekTrimmed.startsWith('/**') || peekTrimmed.startsWith('//')) break
        }
        break
      }
      if (nextLine.startsWith('export ') || nextLine.startsWith('/**')) break
      // If this is a continuation line (starts with | or is same type definition)
      if (allLines[j].startsWith('    ') || allLines[j].startsWith('\t') || allLines[j].startsWith('  |') || allLines[j].startsWith('  ')) {
        body += '\n' + allLines[j]
      } else if (!allLines[j].startsWith(' ') && nextLine && !nextLine.startsWith('|')) {
        break
      }
    }
    const literalRe = /'([^']+)'/g
    const members = new Set<string>()
    for (const lm of body.matchAll(literalRe)) {
      members.add(lm[1])
    }
    if (members.size > 0) {
      results.push({ name, kind: 'type', fields: [], unionMembers: members })
    }
  }

  // Enums
  const enumRe = /export\s+enum\s+(\w+)\s*\{([^}]*)\}/gs
  for (const m of normalized.matchAll(enumRe)) {
    const name = m[1]
    const body = m[2]
    const members = new Set<string>()
    const memberRe = /(\w+)\s*=\s*'([^']+)'/g
    for (const em of body.matchAll(memberRe)) {
      members.add(em[2])
    }
    results.push({ name, kind: 'enum', fields: [], unionMembers: members })
  }

  return results
}

// ─── Python parser — regex-based structural extraction ─────────────────

interface PyField {
  name: string
  required: boolean
  typeHint: string
}

interface PyClassInfo {
  name: string
  fields: PyField[]
}

interface PyLiteralInfo {
  name: string
  members: Set<string>
}

function parsePySource(content: string): { classes: PyClassInfo[]; literals: PyLiteralInfo[] } {
  const classes: PyClassInfo[] = []
  const normalized = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  const lines = normalized.split('\n')

  // Collect class bodies by tracking indent level
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const classMatch = line.match(/^class\s+(\w+)\(.*(?:CanonicalBaseModel|BaseModel).*?\):/)
    if (!classMatch) continue
    const className = classMatch[1]
    const fields: PyField[] = []

    // Collect all lines at 4-space indent until dedent or blank line resets
    for (let j = i + 1; j < lines.length; j++) {
      const fieldLine = lines[j]
      // Stop at dedent (non-indented non-empty line)
      if (fieldLine.trim() && !fieldLine.startsWith('    ') && !fieldLine.startsWith('\t')) break
      // Skip blank lines within class body
      if (!fieldLine.trim()) continue

      const fieldMatch = fieldLine.match(/^\s{4}(\w+):\s*(.+)$/)
      if (!fieldMatch) continue
      const fieldName = fieldMatch[1]
      const rawAnnotation = fieldMatch[2].trim()

      // Skip dunder/method lines
      if (fieldName.startsWith('_')) continue
      if (rawAnnotation.includes('def ') || rawAnnotation.includes('class ')) continue

      // Split type from default
      const eqIdx = rawAnnotation.lastIndexOf(' = ')
      const typeHint = eqIdx >= 0 ? rawAnnotation.slice(0, eqIdx).trim() : rawAnnotation.trim()
      const defaultExpr = eqIdx >= 0 ? rawAnnotation.slice(eqIdx + 3).trim() : ''
      const hasDefault = eqIdx >= 0
      const hasNoneInType = /\bNone\b/.test(typeHint)
      // Truly optional: type includes None OR default is explicitly None
      const isTrulyOptional = hasNoneInType || defaultExpr === 'None'
      // Required: no default AND type doesn't include None
      // Also "required" when default is a non-None factory/list/empty-string (semantically present)
      const required = !hasDefault || (!isTrulyOptional && defaultExpr !== 'None')

      fields.push({ name: fieldName, required, typeHint })
    }
    if (fields.length > 0) {
      classes.push({ name: className, fields })
    }
  }

  // Literal type aliases
  const literals: PyLiteralInfo[] = []
  const literalRe = /(\w+)\s*=\s*Literal\s*\[([^\]]+)\]/g
  for (const m of normalized.matchAll(literalRe)) {
    const name = m[1]
    const body = m[2]
    const members = new Set<string>()
    const memberRe = /"([^"]+)"/g
    for (const lm of body.matchAll(memberRe)) {
      members.add(lm[1])
    }
    literals.push({ name, members })
  }

  return { classes, literals }
}

// ─── Python str Enum parser ────────────────────────────────────────────

interface PyEnumInfo {
  name: string
  members: Map<string, string>  // key → value (for aliases, value is repeated)
  bareValues: Set<string>       // all unique string values
}

function parsePyEnum(content: string, className: string): PyEnumInfo | null {
  const normalized = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  const re = new RegExp(`class\\s+${className}\\([^)]*\\):\\s*\\n((?:\\s{4}.*\\n?)*)`)
  const m = normalized.match(re)
  if (!m) return null
  const body = m[1]
  const members = new Map<string, string>()
  const memberRe = /^\s{4}(\w+)\s*=\s*(?:\w+\.\w+\s*=\s*)?["']([^"']+)["']/gm
  for (const em of body.matchAll(memberRe)) {
    if (em[1] !== em[2]) {
      // Check if it's an alias (like ODD_PHOTO_COUNT = ATTACHMENT2_IMAGE_COUNT_ODD)
      members.set(em[1], em[2])
    } else {
      members.set(em[1], em[1])
    }
  }
  const bareValues = new Set(members.values())
  return { name: className, members, bareValues }
}

// ─── Contract comparison logic ──────────────────────────────────────────

function compareFieldPresence(
  label: string,
  tsFields: TsField[],
  pyFields: PyField[],
  typeName: string,
) {
  const tsNames = new Set(tsFields.map(f => f.name))
  const pyNames = new Set(pyFields.map(f => f.name))

  for (const name of tsNames) {
    if (!pyNames.has(name)) {
      drift(label, 'field-name', `${typeName}.${name}: present in TS, missing in Python`)
    }
  }
  for (const name of pyNames) {
    if (!tsNames.has(name)) {
      drift(label, 'field-name', `${typeName}.${name}: present in Python, missing in TS`)
    }
  }

  // Required/optional
  const tsMap = new Map(tsFields.map(f => [f.name, f.required]))
  const pyMap = new Map(pyFields.map(f => [f.name, f.required]))
  for (const name of tsNames) {
    const tsReq = tsMap.get(name)
    const pyReq = pyMap.get(name)
    if (
      tsReq !== undefined && pyReq !== undefined && tsReq !== pyReq
      && !OPTIONALITY_EXCEPTIONS.has(`${typeName}.${name}`)
    ) {
      drift(label, 'optionality', `${typeName}.${name}: TS ${tsReq ? 'required' : 'optional'}, Python ${pyReq ? 'required' : 'optional'}`)
    }
  }
}

function compareEnumValues(label: string, tsMembers: Set<string>, pyMembers: Set<string>, enumName: string) {
  for (const v of tsMembers) {
    if (!pyMembers.has(v)) {
      drift(label, 'enum-values', `${enumName}: '${v}' in TS, missing in Python`)
    }
  }
  for (const v of pyMembers) {
    if (!tsMembers.has(v)) {
      drift(label, 'enum-values', `${enumName}: '${v}' in Python, missing in TS`)
    }
  }
}

// ─── Error code set comparison ──────────────────────────────────────────

function compareErrorCodeSets() {
  const tsGatePath = path.join(ROOT, 'packages/shared/types/exportGate.ts')
  const pyGatePath = path.join(ROOT, 'packages/backend/app/services/export_gate_service.py')

  if (!fs.existsSync(tsGatePath) || !fs.existsSync(pyGatePath)) return

  const tsContent = fs.readFileSync(tsGatePath, 'utf-8')
  const pyContent = fs.readFileSync(pyGatePath, 'utf-8')

  // Extract TS ExportGateBlockerCode union members
  const tsTypes = parseTsSource(tsContent)
  const tsBlocker = tsTypes.find(t => t.name === 'ExportGateBlockerCode')
  const tsCodes = tsBlocker?.unionMembers ?? new Set<string>()

  // Extract Python ExportGateCode enum values
  const pyEnum = parsePyEnum(pyContent, 'ExportGateCode')
  const pyCodes = pyEnum?.bareValues ?? new Set<string>()

  // For TS, the ExportGateBlockerCode type has the canonical codes
  for (const code of tsCodes) {
    if (!pyCodes.has(code)) {
      drift('error-codes', 'error-code-set', `ExportGateBlockerCode '${code}': in TS type, missing from Python ExportGateCode enum`)
    }
  }
  for (const code of pyCodes) {
    if (!tsCodes.has(code)) {
      drift('error-codes', 'error-code-set', `ExportGateCode '${code}': in Python enum, missing from TS ExportGateBlockerCode`)
    }
  }
}

// ─── Main ────────────────────────────────────────────────────────────────

function main() {
  const tsCanonicalPath = path.join(ROOT, CANONICAL_PAIRS.tsFile)
  const pyCanonicalPath = path.join(ROOT, CANONICAL_PAIRS.pyFile)

  if (!fs.existsSync(tsCanonicalPath)) {
    console.error(`Missing TS source: ${tsCanonicalPath}`)
    process.exit(1)
  }
  if (!fs.existsSync(pyCanonicalPath)) {
    console.error(`Missing Python source: ${pyCanonicalPath}`)
    process.exit(1)
  }

  const tsTypes = parseTsSource(fs.readFileSync(tsCanonicalPath, 'utf-8'))
  const { classes: pyClasses, literals: pyLiterals } = parsePySource(
    fs.readFileSync(pyCanonicalPath, 'utf-8'),
  )

  const tsTypeMap = new Map(tsTypes.map(t => [t.name, t]))
  const pyClassMap = new Map(pyClasses.map(c => [c.name, c]))
  const pyLiteralMap = new Map(pyLiterals.map(l => [l.name, l]))

  // Model pair comparison
  for (const pair of CANONICAL_PAIRS.modelPairs) {
    const pyClass = pyClassMap.get(pair.pyClass)
    if (!pyClass) {
      drift(CANONICAL_PAIRS.label, 'field-name', `${pair.pyClass}: not found in Python source`)
      continue
    }
    // Use explicit tsFields override for nested TS interfaces
    if (pair.tsFields) {
      const tsFieldSet = pair.tsFields
      const pyFieldMap = new Map(pyClass.fields.map(f => [f.name, f.required]))
      for (const tsF of tsFieldSet) {
        const pyReq = pyFieldMap.get(tsF.name)
        if (pyReq === undefined) {
          drift(CANONICAL_PAIRS.label, 'field-name', `${pair.tsType}.${tsF.name}: present in TS, missing in Python`)
        } else if (tsF.required !== pyReq) {
          drift(CANONICAL_PAIRS.label, 'optionality', `${pair.tsType}.${tsF.name}: TS ${tsF.required ? 'required' : 'optional'}, Python ${pyReq ? 'required' : 'optional'}`)
        }
      }
      // Check for Python fields not in TS explicit list
      const tsNameSet = new Set(pair.tsFields.map(f => f.name))
      for (const pyF of pyClass.fields) {
        if (!tsNameSet.has(pyF.name)) {
          drift(CANONICAL_PAIRS.label, 'field-name', `${pair.tsType}.${pyF.name}: present in Python, missing in TS`)
        }
      }
      continue
    }
    const tsType = tsTypeMap.get(pair.tsType)
    if (!tsType) {
      drift(CANONICAL_PAIRS.label, 'field-name', `${pair.tsType}: not found in TS source`)
      continue
    }
    compareFieldPresence(CANONICAL_PAIRS.label, tsType.fields, pyClass.fields, pair.tsType)
  }

  // Enum pair comparison
  for (const pair of CANONICAL_PAIRS.enumPairs) {
    const tsType = tsTypeMap.get(pair.tsType)
    const pyLiteral = pyLiteralMap.get(pair.pyLiteral)
    if (!tsType) {
      drift(CANONICAL_PAIRS.label, 'enum-values', `${pair.tsType}: not found in TS source`)
      continue
    }
    if (!pyLiteral) {
      drift(CANONICAL_PAIRS.label, 'enum-values', `${pair.pyLiteral}: not found in Python source`)
      continue
    }
    compareEnumValues(CANONICAL_PAIRS.label, tsType.unionMembers, pyLiteral.members, pair.tsType)
  }

  // Error code cross-check
  compareErrorCodeSets()

  // Also check DiscSequence model (lives in both canonical_models_service.py and disc_sequence_service.py)
  const tsDiscPath = path.join(ROOT, 'packages/shared/types/discSequence.ts')
  if (fs.existsSync(tsDiscPath)) {
    const tsDiscTypes = parseTsSource(fs.readFileSync(tsDiscPath, 'utf-8'))
    const tsDiscSeq = tsDiscTypes.find(t => t.name === 'DiscSequence')
    const pyDiscSeq = pyClassMap.get('DiscSequence')
    if (tsDiscSeq && pyDiscSeq) {
      compareFieldPresence('disc-sequence', tsDiscSeq.fields, pyDiscSeq.fields, 'DiscSequence')
    }
  }

  // Report
  if (drifts.length === 0) {
    console.log('✅ TS↔Python contract check: no drift detected.\n')
    console.log(`   Checked: ${CANONICAL_PAIRS.modelPairs.length} model pairs, ${CANONICAL_PAIRS.enumPairs.length} enum pairs, error code sets`)
    process.exit(0)
  }

  console.log(`⚠️  Found ${drifts.length} contract drift(s):\n`)
  const byDim: Record<string, Drift[]> = {}
  for (const d of drifts) {
    (byDim[d.dimension] ??= []).push(d)
  }
  for (const [dim, items] of Object.entries(byDim)) {
    console.log(`  [${dim}] (${items.length})`)
    for (const item of items) {
      console.log(`    ${item.detail}`)
    }
  }
  console.log('\n💡 Fix: align the TS type definition with the Python model, or update the contract pair mapping.')
  process.exit(1)
}

main()
