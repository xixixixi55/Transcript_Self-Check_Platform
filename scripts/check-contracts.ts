/**
 * check-contracts.ts — TS↔Python 跨语言契约验证器
 *
 * 比较共享 TypeScript 类型定义与 Python Pydantic 模型及枚举定义，
 * 在字段级漂移进入生产环境前发现问题。
 *
 * 检查维度：
 * 1. 字段存在性 — 每个 TS 字段都必须有对应的 Python 字段（反之亦然）
 * 2. 必选/可选 — 可选性标记必须一致
 * 3. 枚举值 — 字面量联合/枚举成员集合必须完全相同
 * 4. 错误码成员 — ExportGateBlockerCode 必须等于 ExportGateCode 的值
 *
 * 用法：
 *   npx tsx scripts/check-contracts.ts
 * 退出码：0 = 一致，1 = 检测到漂移
 */

import * as fs from 'node:fs'
import * as path from 'node:path'

const ROOT = path.resolve(__dirname, '..')

// ─── 契约对：TS 源码 → Python 源码 ─────────────────────────────────────

interface ContractPair {
  label: string
  tsFile: string          // relative to ROOT
  pyFile: string          // relative to ROOT
  /** 字段必须与 Python 类字段匹配的 TS 类型名称 */
  modelPairs: { tsType: string; pyClass: string; tsFields?: { name: string; required: boolean }[] }[]
  /** 用于枚举比较的 TS 类型名称 → Python Literal 名称 */
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
    // CanonicalCaseInfo：仅检查 TS 顶层字段；嵌套 introduction 字段通过 CanonicalCaseIntroduction 契约对检查
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
    // CanonicalCaseIntroduction：TS 定义嵌套在 CanonicalCaseInfo 中
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
    // ProcessStep：TS 使用内联结构，Python 使用命名模型
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
    // ExtractListColumn + ExtractListTable：TS 内联在 CanonicalAttachmentInputs.extract_list 中
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

// 这些可编辑 TS 输入可以省略 Python 规范序列化器始终以空字符串默认值实体化的字段。
// 这种不对称是有意设计；其他所有必选/可选不匹配仍属于契约漂移。
const OPTIONALITY_EXCEPTIONS = new Set([
  'Material.unextractable_reason',
  'InspectorSnapshot.position',
])

// ─── 漂移报告 ──────────────────────────────────────────────────────────

interface Drift {
  contract: string
  dimension: 'field-name' | 'optionality' | 'enum-values' | 'error-code-set'
  detail: string
}

const drifts: Drift[] = []

function drift(contract: string, dimension: Drift['dimension'], detail: string) {
  drifts.push({ contract, dimension, detail })
}

// ─── TS 解析器 — 基于正则表达式的结构提取 ─────────────────────────────

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

  // 接口：从 "export interface Name {" 匹配到配对的 "}"（保持平衡）
  const ifaceRe = /export\s+interface\s+(\w+)\s*\{/gs
  for (const m of normalized.matchAll(ifaceRe)) {
    const name = m[1]
    const startIdx = m.index! + m[0].length
    // 查找配对的右花括号
    let depth = 1
    let endIdx = startIdx
    for (let i = startIdx; i < normalized.length && depth > 0; i++) {
      if (normalized[i] === '{') depth++
      else if (normalized[i] === '}') depth--
      if (depth === 0) endIdx = i
    }
    const body = normalized.slice(startIdx, endIdx)
    const fields: TsField[] = []
    // 匹配字段行：name?: type; 或 name: type;
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

  // 类型别名（字面量联合）：同时处理单行和多行形式。
  // 逐行解析：从 "export type Name =" 开始，在下一个 "export" 或“空行 + 非缩进行”前结束。
  const typeStartRe = /export\s+type\s+(\w+)\s*=\s*(.*)/g
  for (const ms of normalized.matchAll(typeStartRe)) {
    const name = ms[1]
    if (results.some(r => r.name === name)) continue  // skip if already captured
    const firstLine = ms[2]
    // 收集续行（以空白和 | 开头）
    const startLineNum = normalized.slice(0, ms.index).split('\n').length
    const allLines = normalized.split('\n')
    let body = firstLine
    for (let j = startLineNum; j < allLines.length; j++) {
      const nextLine = allLines[j].trim()
      // 遇到下一个 export、注释、后接非续行的空行或非空白开头的行时停止
      if (!nextLine) {
        // 空行：检查下一非空行是否以 export 或 class 开头
        let peek = j + 1
        while (peek < allLines.length && !allLines[peek].trim()) peek++
        if (peek < allLines.length) {
          const peekTrimmed = allLines[peek].trim()
          if (peekTrimmed.startsWith('export ') || peekTrimmed.startsWith('/**') || peekTrimmed.startsWith('//')) break
        }
        break
      }
      if (nextLine.startsWith('export ') || nextLine.startsWith('/**')) break
      // 若当前行是续行（以 | 开头或属于同一类型定义）
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

  // 枚举
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

// ─── Python 解析器 — 基于正则表达式的结构提取 ─────────────────────────

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

  // 通过跟踪缩进级别收集类体
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const classMatch = line.match(/^class\s+(\w+)\(.*(?:CanonicalBaseModel|BaseModel).*?\):/)
    if (!classMatch) continue
    const className = classMatch[1]
    const fields: PyField[] = []

    // 收集所有 4 空格缩进的行，直至缩进减少或空行重置
    for (let j = i + 1; j < lines.length; j++) {
      const fieldLine = lines[j]
      // 缩进减少时停止（无缩进的非空行）
      if (fieldLine.trim() && !fieldLine.startsWith('    ') && !fieldLine.startsWith('\t')) break
      // 跳过类体内的空行
      if (!fieldLine.trim()) continue

      const fieldMatch = fieldLine.match(/^\s{4}(\w+):\s*(.+)$/)
      if (!fieldMatch) continue
      const fieldName = fieldMatch[1]
      const rawAnnotation = fieldMatch[2].trim()

      // 跳过双下划线/方法行
      if (fieldName.startsWith('_')) continue
      if (rawAnnotation.includes('def ') || rawAnnotation.includes('class ')) continue

      // 分离类型与默认值
      const eqIdx = rawAnnotation.lastIndexOf(' = ')
      const typeHint = eqIdx >= 0 ? rawAnnotation.slice(0, eqIdx).trim() : rawAnnotation.trim()
      const defaultExpr = eqIdx >= 0 ? rawAnnotation.slice(eqIdx + 3).trim() : ''
      const hasDefault = eqIdx >= 0
      const hasNoneInType = /\bNone\b/.test(typeHint)
      // 真正可选：类型包含 None，或默认值显式为 None
      const isTrulyOptional = hasNoneInType || defaultExpr === 'None'
      // 必选：无默认值且类型不含 None
      // 默认值为非 None 的工厂/列表/空字符串时也视为“必选”（语义上存在）
      const required = !hasDefault || (!isTrulyOptional && defaultExpr !== 'None')

      fields.push({ name: fieldName, required, typeHint })
    }
    if (fields.length > 0) {
      classes.push({ name: className, fields })
    }
  }

  // Literal 类型别名
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

// ─── Python str 枚举解析器 ─────────────────────────────────────────────

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
      // 检查是否为别名（如 ODD_PHOTO_COUNT = ATTACHMENT2_IMAGE_COUNT_ODD）
      members.set(em[1], em[2])
    } else {
      members.set(em[1], em[1])
    }
  }
  const bareValues = new Set(members.values())
  return { name: className, members, bareValues }
}

// ─── 契约比较逻辑 ──────────────────────────────────────────────────────

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

  // 必选/可选
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

// ─── 错误码集合比较 ────────────────────────────────────────────────────

function compareErrorCodeSets() {
  const tsGatePath = path.join(ROOT, 'packages/shared/types/exportGate.ts')
  const pyGatePath = path.join(ROOT, 'packages/backend/app/services/export_gate_service.py')

  if (!fs.existsSync(tsGatePath) || !fs.existsSync(pyGatePath)) return

  const tsContent = fs.readFileSync(tsGatePath, 'utf-8')
  const pyContent = fs.readFileSync(pyGatePath, 'utf-8')

  // 提取 TS ExportGateBlockerCode 联合成员
  const tsTypes = parseTsSource(tsContent)
  const tsBlocker = tsTypes.find(t => t.name === 'ExportGateBlockerCode')
  const tsCodes = tsBlocker?.unionMembers ?? new Set<string>()

  // 提取 Python ExportGateCode 枚举值
  const pyEnum = parsePyEnum(pyContent, 'ExportGateCode')
  const pyCodes = pyEnum?.bareValues ?? new Set<string>()

  // 在 TS 中，ExportGateBlockerCode 类型包含规范错误码
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

// ─── 主流程 ────────────────────────────────────────────────────────────

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

  // 模型对比较
  for (const pair of CANONICAL_PAIRS.modelPairs) {
    const pyClass = pyClassMap.get(pair.pyClass)
    if (!pyClass) {
      drift(CANONICAL_PAIRS.label, 'field-name', `${pair.pyClass}: not found in Python source`)
      continue
    }
    // 对嵌套 TS 接口使用显式 tsFields 覆盖值
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
      // 检查未出现在 TS 显式列表中的 Python 字段
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

  // 枚举对比较
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

  // 错误码交叉检查
  compareErrorCodeSets()

  // 同时检查 DiscSequence 模型（同时存在于 canonical_models_service.py 和 disc_sequence_service.py）
  const tsDiscPath = path.join(ROOT, 'packages/shared/types/discSequence.ts')
  if (fs.existsSync(tsDiscPath)) {
    const tsDiscTypes = parseTsSource(fs.readFileSync(tsDiscPath, 'utf-8'))
    const tsDiscSeq = tsDiscTypes.find(t => t.name === 'DiscSequence')
    const pyDiscSeq = pyClassMap.get('DiscSequence')
    if (tsDiscSeq && pyDiscSeq) {
      compareFieldPresence('disc-sequence', tsDiscSeq.fields, pyDiscSeq.fields, 'DiscSequence')
    }
  }

  // 报告
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
