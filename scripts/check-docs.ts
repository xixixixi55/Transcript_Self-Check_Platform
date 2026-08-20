/**
 * check-docs.ts — 文档与代码一致性检查器
 *
 * 检查内容：
 * 1.  [E-A1] 目录结构：directory.md vs 实际文件系统
 * 2.  [补充] npm 命令：AGENTS.md 声明 vs package.json
 * 3.  [补充] 已完成 tasks.md 文件引用 vs 实际存在性            [strict]
 * 4.  [补充] 必选任务完成状态（只读取显式 checklist 标记）     [strict]
 * 5.  [补充] specs 能力目录 vs directory.md/AGENTS.md 中列出的能力名 [strict]
 * 6.  [E-A2] [按需] data-model.md 接口字段 vs 类型定义文件实际字段
 * 7.  [补充] AGENTS.md 行数预算（所有模式阻断）
 * 8.  [E-A3] 文档链接有效性
 * 9.  [E-A4] OpenSpec 版本一致性                              [strict]
 * 10. [E-A5] TEMPLATE_CANDIDATE 积压统计                      [strict]
 * 11. [E-A6] 迭代记录教训反哺完整性                           [strict]
 * 12. [补充] 高频 Harness 入口渐进式上下文合同（所有模式阻断）
 *
 * 用法：
 *   npx tsx scripts/check-docs.ts             默认模式（低噪音检查）
 *   npx tsx scripts/check-docs.ts --strict --change <name> 当前变更严格模式
 *   npx tsx scripts/check-docs.ts --strict --all         全局严格模式
 * 退出码：0 = 通过，1 = 存在偏差
 */

import * as fs from 'node:fs'
import * as path from 'node:path'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import {
  getLineBudgetOverflow,
  getCompletedTaskFileReferences,
  getManagedAgentToolingFiles,
  getRequiredIncompleteTasks,
  getWorkflowMetadata,
  parseWorkflowLevel,
  validateDeltaSpec,
  validateProgressiveContextCommand,
  type WorkflowLevel,
} from './check-docs-utils'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// ─── PROJECT CONFIG (generated from harness.config.yaml) ─────────

const ROOT = path.resolve(__dirname, '..')

/** 源码根目录列表 */
const SRC_ROOTS: { dir: string; extensions: string[] }[] = [
  { dir: path.join(ROOT, 'packages/shared'), extensions: ['.ts'] },
  { dir: path.join(ROOT, 'packages/frontend/src'), extensions: ['.ts', '.tsx'] },
  { dir: path.join(ROOT, 'packages/backend/app'), extensions: ['.py'] },
]

const DOCS_DIR = path.resolve(ROOT, 'harness')
const OPENSPEC_DIR = path.resolve(ROOT, 'openspec')
const AGENTS_MD = path.resolve(ROOT, 'AGENTS.md')
const DIRECTORY_MD = path.join(DOCS_DIR, 'directory.md')

/** 期望的命令列表 */
const EXPECTED_COMMANDS: string[] = [
  'dev', 'build', 'lint:arch', 'typecheck', 'test', 'test:frontend', 'test:backend',
  'test:governance', 'verify:quick', 'verify:frontend', 'verify:backend', 'verify:full', 'verify:full:all', 'verify', 'verify:docs',
  'verify:docs:strict', 'verify:docs:strict:all', 'check:repository-assets', 'check-docs', 'pre-commit',
]

/** 期望的源码目录（相对于各 SRC_ROOT，key 为 SRC_ROOT 索引） */
const EXPECTED_DIRS: Record<number, string[]> = {
  0: ['types', 'constants', 'utils', '__tests__'],              // packages/shared
  1: ['hooks', 'components', 'pages', '__tests__'],             // packages/frontend/src
  2: ['repository', 'services', 'controllers', 'routes', 'data'], // packages/backend/app
}

// 根规则入口保持精简；详细执行说明应下沉到 Harness 专用文档。
const AGENTS_MAX_LINES = 250

const PROGRESSIVE_CONTEXT_COMMANDS = [
  '.agents/commands/harness/propose.md',
  '.agents/commands/harness/apply.md',
  '.agents/commands/harness/fix.md',
  '.agents/commands/harness/verify.md',
]

/** 数据模型 spec 路径 */
const DATA_MODEL_MD = path.join(OPENSPEC_DIR, 'specs', 'data-model.md')

/** 类型定义目录 */
const TYPES_DIR = path.join(ROOT, 'packages/shared/types')

// ─── MODE ──────────────────────────────────────────────────────

const STRICT_MODE = process.argv.includes('--strict')
const SHOW_DETAILS = process.argv.includes('--details')
const ALL_SCOPE = process.argv.includes('--all')

function getOptionValue(name: string): string | undefined {
  const exactIndex = process.argv.indexOf(name)
  if (exactIndex >= 0) return process.argv[exactIndex + 1]
  const prefix = `${name}=`
  const inline = process.argv.find((arg) => arg.startsWith(prefix))
  return inline?.slice(prefix.length)
}

/** Strict task checks require an explicit current-change or all-active scope. */
const CHANGE_NAME = getOptionValue('--change')

// ─── END PROJECT CONFIG ──────────────────────────────────────────

type DriftType =
  | 'missing-in-code' | 'missing-in-docs' | 'command-missing'
  | 'task-file-missing' | 'task-incomplete' | 'spec-not-listed' | 'file-not-in-tree'
  | 'type-drift' | 'broken-link' | 'version-mismatch'
  | 'template-candidate-backlog' | 'lesson-not-fed-back'
  | 'agents-md-line-budget' | 'workflow-level-missing' | 'workflow-level-invalid'
  | 'level2-delta-spec-missing' | 'delta-spec-invalid'
  | 'legacy-reconciliation-invalid' | 'agent-tooling-mirror-drift'
  | 'harness-context-loading-regression'

interface Drift { type: DriftType; message: string }

function printDriftCounts(drifts: Drift[]): void {
  const counts = new Map<DriftType, number>()
  for (const drift of drifts) counts.set(drift.type, (counts.get(drift.type) ?? 0) + 1)

  if (counts.size === 0) return

  console.log('Drift counts:')
  for (const [type, count] of [...counts.entries()].sort(([left], [right]) => left.localeCompare(right))) {
    console.log(`  [${type}] ${count}`)
  }
}

function printDriftDetails(drifts: Drift[]): void {
  if (drifts.length === 0) return
  console.log(`\n⚠️  Found ${drifts.length} drift(s):\n`)
  for (const drift of drifts) console.log(`  [${drift.type}] ${drift.message}`)
}

// ─── Helpers ────────────────────────────────

function getAllFiles(dir: string, ext: string[], prefix = ''): string[] {
  const results: string[] = []
  if (!fs.existsSync(dir)) return results
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const rel = prefix ? `${prefix}/${entry.name}` : entry.name
    if (entry.isDirectory()) results.push(...getAllFiles(path.join(dir, entry.name), ext, rel))
    else if (ext.some((e) => entry.name.endsWith(e))) results.push(rel)
  }
  return results
}

function getAllRelativeFiles(dir: string, prefix = ''): string[] {
  const results: string[] = []
  if (!fs.existsSync(dir)) return results
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const rel = prefix ? `${prefix}/${entry.name}` : entry.name
    if (entry.isDirectory()) results.push(...getAllRelativeFiles(path.join(dir, entry.name), rel))
    else results.push(rel)
  }
  return results
}

function toPosixPath(value: string): string {
  return value.replaceAll('\\', '/')
}

function readNormalizedText(filePath: string): string {
  return fs.readFileSync(filePath, 'utf-8').replaceAll('\r\n', '\n').replaceAll('\r', '\n')
}

function getActualDirs(baseDir: string, prefix = ''): string[] {
  const dirs: string[] = []
  if (!fs.existsSync(baseDir)) return dirs
  for (const entry of fs.readdirSync(baseDir, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      const skipDirs = ['node_modules', 'dist', '__pycache__', '.pytest_cache', '.venv']
      if (skipDirs.includes(entry.name)) continue
      const rel = prefix ? `${prefix}/${entry.name}` : entry.name
      dirs.push(rel)
      dirs.push(...getActualDirs(path.join(baseDir, entry.name), rel))
    }
  }
  return dirs
}

function readFileIfExists(p: string): string {
  return fs.existsSync(p) ? fs.readFileSync(p, 'utf-8') : ''
}

// ─── Check 1: 目录结构 vs directory.md ──────

function checkDirectoryStructure(): Drift[] {
  const drifts: Drift[] = []
  SRC_ROOTS.forEach((srcRoot, idx) => {
    const actualDirs = getActualDirs(srcRoot.dir)
    const rootLabel = path.relative(ROOT, srcRoot.dir)
    const expectedForRoot = EXPECTED_DIRS[idx] || []
    for (const dir of actualDirs) {
      if (dir.includes('/')) continue
      if (!expectedForRoot.some((e) => e === dir || e.startsWith(dir + '/')))
        drifts.push({ type: 'missing-in-docs', message: `Directory "${rootLabel}/${dir}/" exists but not in directory.md` })
    }
  })
  return drifts
}

// ─── Check 2: npm 命令 vs AGENTS.md ─────────

function checkCommands(): Drift[] {
  const drifts: Drift[] = []
  const pkgPath = path.join(ROOT, 'package.json')
  if (!fs.existsSync(pkgPath)) return drifts
  const scripts = Object.keys(JSON.parse(fs.readFileSync(pkgPath, 'utf-8')).scripts || {})
  for (const cmd of EXPECTED_COMMANDS) {
    if (!scripts.includes(cmd))
      drifts.push({ type: 'command-missing', message: `AGENTS.md declares "${cmd}" but script not found in package.json` })
  }
  return drifts
}

// ─── Check 3/4: active tasks.md scope and status ──

interface ActiveTaskFile {
  changeName: string
  tasksPath: string
  content: string
}

interface ActiveChangeMetadata extends ActiveTaskFile {
  workflowLevel?: WorkflowLevel
  rawWorkflowLevel?: string
  legacyMigration?: boolean
  rawLegacyMigration?: string
  specSyncStatus?: string
  specSyncEvidence?: string
  deltaSpecPaths: string[]
}

function getActiveTaskFiles(changeName?: string): ActiveTaskFile[] {
  const changesDir = path.join(OPENSPEC_DIR, 'changes')
  if (changeName) {
    const tasksPath = path.join(changesDir, changeName, 'tasks.md')
    return [{ changeName, tasksPath, content: readFileIfExists(tasksPath) }]
  }

  if (!fs.existsSync(changesDir)) return []
  return fs.readdirSync(changesDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && entry.name !== 'archive')
    .map((entry) => {
      const tasksPath = path.join(changesDir, entry.name, 'tasks.md')
      return { changeName: entry.name, tasksPath, content: readFileIfExists(tasksPath) }
    })
}

function getDeltaSpecPaths(changeName: string): string[] {
  const specsDir = path.join(OPENSPEC_DIR, 'changes', changeName, 'specs')
  return getAllRelativeFiles(specsDir)
    .filter((filePath) => path.basename(filePath).toLowerCase() === 'spec.md')
    .map((filePath) => toPosixPath(path.posix.join('specs', filePath)))
}

function getActiveChangeMetadata(changeName?: string): ActiveChangeMetadata[] {
  return getActiveTaskFiles(changeName).map((taskFile) => {
    const rawWorkflowLevel = getWorkflowMetadata(taskFile.content, 'workflow_level')
    const rawLegacyMigration = getWorkflowMetadata(taskFile.content, 'legacy_migration')
    const rawSpecSyncStatus = getWorkflowMetadata(taskFile.content, 'spec_sync_status')
    const rawSpecSyncEvidence = getWorkflowMetadata(taskFile.content, 'spec_sync_evidence')
    return {
      ...taskFile,
      workflowLevel: parseWorkflowLevel(taskFile.content),
      rawWorkflowLevel,
      legacyMigration: rawLegacyMigration === 'true' ? true : rawLegacyMigration === 'false' ? false : undefined,
      rawLegacyMigration,
      specSyncStatus: rawSpecSyncStatus,
      specSyncEvidence: rawSpecSyncEvidence,
      deltaSpecPaths: getDeltaSpecPaths(taskFile.changeName),
    }
  })
}

function checkTaskFiles(): Drift[] {
  const drifts: Drift[] = []
  for (const taskFile of getActiveTaskFiles(CHANGE_NAME)) {
    if (!taskFile.content) {
      drifts.push({ type: 'task-file-missing', message: `${taskFile.changeName}: tasks.md is missing` })
      continue
    }
    for (const filePath of getCompletedTaskFileReferences(taskFile.content)) {
      if (filePath.includes('*') || filePath.includes('<')) continue
      if (filePath.includes('/') && !fs.existsSync(path.join(ROOT, filePath)))
        drifts.push({ type: 'missing-in-code', message: `${taskFile.changeName}: tasks.md references "${filePath}" but file does not exist` })
    }
  }
  return drifts
}

// ─── Check 4: 必选 tasks.md 完成状态 ─────────

function checkRequiredTaskCompletion(): Drift[] {
  const drifts: Drift[] = []
  for (const taskFile of getActiveTaskFiles(CHANGE_NAME)) {
    for (const task of getRequiredIncompleteTasks(taskFile.content)) {
      drifts.push({
        type: 'task-incomplete',
        message: `${taskFile.changeName}: required task at line ${task.lineNumber} is not checked — ${task.text}`,
      })
    }
  }
  return drifts
}

// ─── Check 4b: workflow level and delta spec contract ─────────────

function checkWorkflowLevelAndDeltaSpecs(): Drift[] {
  const drifts: Drift[] = []
  for (const change of getActiveChangeMetadata(CHANGE_NAME)) {
    if (!change.content) continue

    if (!change.rawWorkflowLevel) {
      drifts.push({
        type: 'workflow-level-missing',
        message: `${change.changeName}: tasks.md must persist workflow_level: 2 or workflow_level: 3`,
      })
      continue
    }
    if (!change.workflowLevel) {
      drifts.push({
        type: 'workflow-level-invalid',
        message: `${change.changeName}: workflow_level must be exactly 2 or 3 (found "${change.rawWorkflowLevel}")`,
      })
      continue
    }

    if (change.rawLegacyMigration && change.legacyMigration === undefined) {
      drifts.push({
        type: 'legacy-reconciliation-invalid',
        message: `${change.changeName}: legacy_migration must be true or false when present`,
      })
    }

    const validSyncStatuses = new Set(['pending', 'partial', 'reconciled'])
    if (change.specSyncStatus && !validSyncStatuses.has(change.specSyncStatus)) {
      drifts.push({
        type: 'legacy-reconciliation-invalid',
        message: `${change.changeName}: spec_sync_status must be pending, partial, or reconciled`,
      })
    }
    if (change.specSyncStatus === 'reconciled' && !change.specSyncEvidence) {
      drifts.push({
        type: 'legacy-reconciliation-invalid',
        message: `${change.changeName}: spec_sync_status: reconciled requires spec_sync_evidence`,
      })
    }
    if (change.legacyMigration === true && !change.specSyncStatus) {
      drifts.push({
        type: 'legacy-reconciliation-invalid',
        message: `${change.changeName}: legacy_migration: true requires spec_sync_status`,
      })
    }

    if (change.workflowLevel === 2 && /^\s*Spec impact:\s*N\/A\s*$/im.test(change.content)) {
      drifts.push({
        type: 'level2-delta-spec-missing',
        message: `${change.changeName}: Level 2 cannot use "Spec impact: N/A"; reclassify as Level 1 when there is no behavior delta`,
      })
    }

    if (change.workflowLevel === 2) {
      const hasReconciledHistoricalSpec =
        change.legacyMigration === true &&
        change.specSyncStatus === 'reconciled' &&
        Boolean(change.specSyncEvidence)
      if (change.deltaSpecPaths.length === 0 && !hasReconciledHistoricalSpec) {
        drifts.push({
          type: 'level2-delta-spec-missing',
          message: `${change.changeName}: workflow_level 2 requires at least one specs/<capability>/spec.md delta spec`,
        })
      }

      for (const deltaSpecPath of change.deltaSpecPaths) {
        const deltaContent = readFileIfExists(path.join(OPENSPEC_DIR, 'changes', change.changeName, deltaSpecPath))
        const formatErrors = validateDeltaSpec(deltaContent)
        for (const formatError of formatErrors) {
          drifts.push({
            type: 'delta-spec-invalid',
            message: `${change.changeName}: ${deltaSpecPath} ${formatError}`,
          })
        }
      }
    }
  }
  return drifts
}

// ─── Check 4c: .agents/.claude mirror contract ───────────────────

function checkAgentToolingMirror(): Drift[] {
  const drifts: Drift[] = []
  const agentsDir = path.join(ROOT, '.agents')
  const claudeDir = path.join(ROOT, '.claude')
  const managedFiles = execFileSync(
    'git',
    ['ls-files', '--cached', '--others', '--exclude-standard', '--', '.agents', '.claude'],
    { cwd: ROOT, encoding: 'utf8' },
  ).split(/\r?\n/).filter(Boolean)
  const { agentsFiles, claudeFiles } = getManagedAgentToolingFiles(managedFiles)
  const relativeFiles = [...new Set([...agentsFiles, ...claudeFiles])].sort()

  for (const relativeFile of relativeFiles) {
    const agentsPath = path.join(agentsDir, relativeFile)
    const claudePath = path.join(claudeDir, relativeFile)
    if (!fs.existsSync(agentsPath)) {
      drifts.push({
        type: 'agent-tooling-mirror-drift',
        message: `.claude/${relativeFile} has no matching .agents/${relativeFile}`,
      })
      continue
    }
    if (!fs.existsSync(claudePath)) {
      drifts.push({
        type: 'agent-tooling-mirror-drift',
        message: `.agents/${relativeFile} has no matching .claude/${relativeFile}`,
      })
      continue
    }
    if (readNormalizedText(agentsPath) !== readNormalizedText(claudePath)) {
      drifts.push({
        type: 'agent-tooling-mirror-drift',
        message: `.agents/${relativeFile} and .claude/${relativeFile} differ after line-ending normalization`,
      })
    }
  }
  return drifts
}

// ─── Check 4d: high-frequency Harness context loading contract ──

function checkHarnessContextLoading(): Drift[] {
  const drifts: Drift[] = []
  for (const relativePath of PROGRESSIVE_CONTEXT_COMMANDS) {
    const content = readFileIfExists(path.join(ROOT, relativePath))
    if (!content) {
      drifts.push({
        type: 'harness-context-loading-regression',
        message: `${relativePath} is missing`,
      })
      continue
    }
    for (const error of validateProgressiveContextCommand(content)) {
      drifts.push({
        type: 'harness-context-loading-regression',
        message: `${relativePath}: ${error}`,
      })
    }
  }
  return drifts
}

// ─── Check 5: specs vs directory.md ─────────

function checkSpecsListed(): Drift[] {
  const drifts: Drift[] = []
  const specsDir = path.join(OPENSPEC_DIR, 'specs')
  if (!fs.existsSync(specsDir)) return drifts
  const dirMd = readFileIfExists(DIRECTORY_MD) + readFileIfExists(AGENTS_MD)

  for (const spec of getAllFiles(specsDir, ['.md'])) {
    if (path.basename(spec) !== 'spec.md') continue
    const capabilityName = path.dirname(spec)
    if (!dirMd.includes(capabilityName))
      drifts.push({ type: 'spec-not-listed', message: `openspec/specs/${spec} exists but capability "${capabilityName}" not in directory.md` })
  }
  return drifts
}

// ─── Check 6 [E-A2]: data-model.md vs 类型定义 ─

function checkDataModelConsistency(): Drift[] {
  const drifts: Drift[] = []
  const dmContent = readFileIfExists(DATA_MODEL_MD)
  if (!dmContent || !TYPES_DIR || !fs.existsSync(TYPES_DIR)) return drifts

  const typeFiles = getAllFiles(TYPES_DIR, ['.ts', '.tsx'])
  const tsContent = typeFiles.map(f => readFileIfExists(path.join(TYPES_DIR, f))).join('\n')
  if (!tsContent) return drifts

  const dmInterfaces = [
    ...dmContent.matchAll(/(?:interface|type|enum)\s+(\w+)/g),
    ...dmContent.matchAll(/###\s+.*[（(](\w+)[）)]/g),
  ].map((m) => m[1])
  const tsInterfaces = [...tsContent.matchAll(/export\s+(?:interface|type|enum)\s+(\w+)/g)].map((m) => m[1])

  for (const iface of dmInterfaces) {
    if (!tsInterfaces.includes(iface))
      drifts.push({ type: 'type-drift', message: `data-model.md defines "${iface}" but not found in types directory` })
  }
  for (const iface of tsInterfaces) {
    if (!dmInterfaces.includes(iface))
      drifts.push({ type: 'type-drift', message: `Types directory exports "${iface}" but not documented in data-model.md` })
  }
  return drifts
}

// ─── Check 7: AGENTS.md 行数限制 ───────────

function checkAgentsSize(): Drift[] {
  const content = readFileIfExists(AGENTS_MD)
  if (!content) return []
  const lines = getLineBudgetOverflow(content, AGENTS_MAX_LINES)
  if (lines !== undefined) {
    return [{
      type: 'agents-md-line-budget',
      message: `AGENTS.md has ${lines} lines, exceeds limit of ${AGENTS_MAX_LINES}.`,
    }]
  }
  return []
}

// ─── Check 8 [E-A3]: 文档链接有效性 ────────

function checkDocLinks(): Drift[] {
  const drifts: Drift[] = []
  const docsToScan = [
    AGENTS_MD,
    ...fs.existsSync(DOCS_DIR)
      ? fs.readdirSync(DOCS_DIR).filter(f => f.endsWith('.md')).map(f => path.join(DOCS_DIR, f))
      : [],
  ]

  for (const docPath of docsToScan) {
    const content = readFileIfExists(docPath)
    if (!content) continue
    const docLabel = path.relative(ROOT, docPath)
    const linkPatterns = [
      /`((?:harness|openspec|scripts|\.claude)\/[^`]+)`/g,
    ]
    for (const pattern of linkPatterns) {
      for (const match of content.matchAll(pattern)) {
        const refPath = match[1]
        if (refPath.includes('*') || refPath.includes('<')) continue
        if (!fs.existsSync(path.join(ROOT, refPath))) {
          drifts.push({ type: 'broken-link', message: `${docLabel} references "${refPath}" but path does not exist` })
        }
      }
    }
  }
  return drifts
}

// ─── Check 9 [E-A4]: OpenSpec 版本一致性 ────

function checkOpenSpecVersion(): Drift[] {
  const drifts: Drift[] = []
  const configContent = readFileIfExists(path.join(OPENSPEC_DIR, 'config.yaml'))
  const guideContent = readFileIfExists(path.join(DOCS_DIR, 'iteration-guide.md'))
  if (!configContent || !guideContent) return drifts

  const configMatch = configContent.match(/openspec_version:\s*["']?([^"'\s]+)["']?/)
  const guideMatch = guideContent.match(/基于\s*OpenSpec\s*(\d+\.\d+\.\d+)/)

  if (configMatch?.[1] && guideMatch?.[1] && configMatch[1] !== guideMatch[1]) {
    drifts.push({
      type: 'version-mismatch',
      message: `OpenSpec version mismatch: config.yaml="${configMatch[1]}" vs iteration-guide.md="${guideMatch[1]}"`,
    })
  }
  return drifts
}

// ─── Check 10 [E-A5]: TEMPLATE_CANDIDATE 积压 ──

const TEMPLATE_CANDIDATE_LIMIT = 5

function checkTemplateCandidateBacklog(): Drift[] {
  const drifts: Drift[] = []
  const iterDir = path.join(DOCS_DIR, 'archive', 'iterations')
  if (!fs.existsSync(iterDir)) return drifts

  let pendingCount = 0
  for (const file of fs.readdirSync(iterDir).filter(f => f.endsWith('.md'))) {
    const content = fs.readFileSync(path.join(iterDir, file), 'utf-8')
    const matches = content.match(/TEMPLATE_CANDIDATE[\s\S]*?状态：\s*pending/gi)
    if (matches) pendingCount += matches.length
  }

  if (pendingCount > TEMPLATE_CANDIDATE_LIMIT) {
    drifts.push({
      type: 'template-candidate-backlog',
      message: `${pendingCount} pending TEMPLATE_CANDIDATE entries (limit: ${TEMPLATE_CANDIDATE_LIMIT}).`,
    })
  }
  return drifts
}

// ─── Check 11 [E-A6]: 迭代记录教训反哺完整性 ──

function checkLessonFeedback(): Drift[] {
  const drifts: Drift[] = []
  const iterDir = path.join(DOCS_DIR, 'archive', 'iterations')
  if (!fs.existsSync(iterDir)) return drifts

  const files = fs.readdirSync(iterDir).filter(f => f.endsWith('.md')).sort()
  if (files.length === 0) return drifts

  const latestFile = files[files.length - 1]
  const content = fs.readFileSync(path.join(iterDir, latestFile), 'utf-8')

  const lessonSection = content.match(/##\s*💡\s*沉淀的经验\s*\n([\s\S]*?)(?=\n##\s|$)/)
  const feedbackSection = content.match(/##\s*✅\s*已反哺到 Harness[\s\S]*?\n([\s\S]*?)(?=\n##\s|$)/)

  const hasLessons = lessonSection && lessonSection[1].trim().length > 0
  const hasFeedback = feedbackSection && feedbackSection[1].trim().length > 0

  if (hasLessons && !hasFeedback) {
    drifts.push({
      type: 'lesson-not-fed-back',
      message: `${latestFile}: has lessons but no feedback recorded.`,
    })
  }
  return drifts
}

// ─── Main ────────────────────────────────────

function main() {
  if (STRICT_MODE && ALL_SCOPE && CHANGE_NAME) {
    console.error('Strict docs scope error: use either --all or --change <name>, not both.')
    process.exit(2)
  }
  if (STRICT_MODE && !ALL_SCOPE && !CHANGE_NAME) {
    console.error('Strict docs scope error: use --change <name> or use --all.')
    process.exit(2)
  }

  const modeLabel = STRICT_MODE ? 'strict (all checks)' : 'quick (low-noise checks)'
  const scopeLabel = CHANGE_NAME ? `change:${CHANGE_NAME}` : ALL_SCOPE ? 'all-active-changes' : 'default'
  console.log(`🔍 Documentation Drift Check — mode: ${modeLabel} | task scope: ${scopeLabel}\n`)

  // Default mode: core checks only
  const allDrifts: Drift[] = [
    ...checkDirectoryStructure(),          // E-A1
    ...checkCommands(),                    // npm commands
    ...checkDataModelConsistency(),        // E-A2
    ...checkAgentsSize(),                  // AGENTS.md hard line budget
    ...checkDocLinks(),                    // E-A3
    ...checkAgentToolingMirror(),          // mirrored command/skill source
    ...checkHarnessContextLoading(),       // progressive context loading contract
  ]

  const checks = [
    'E-A1:directory-structure', 'npm-commands',
    'E-A2:data-model-consistency', 'agents-md-size', 'E-A3:doc-links', 'agent-tooling-mirror',
    'harness-context-loading',
  ]

  // Strict mode: add governance checks
  if (STRICT_MODE) {
    allDrifts.push(
      ...checkTaskFiles(),
      ...checkRequiredTaskCompletion(),
      ...checkWorkflowLevelAndDeltaSpecs(),
      ...checkSpecsListed(),
      ...checkOpenSpecVersion(),
      ...checkTemplateCandidateBacklog(),
      ...checkLessonFeedback(),
    )
    checks.push(
      'task-file-refs', 'required-task-completion', 'workflow-level-and-delta-spec', 'specs-listed',
      'E-A4:openspec-version', 'E-A5:template-candidate-backlog', 'E-A6:lesson-feedback',
    )
  }

  const severe = allDrifts
  console.log(`Summary: ${severe.length === 0 ? 'PASS' : 'FAIL'} | checks=${checks.length} | drifts=${severe.length}`)

  if (severe.length === 0) {
    console.log('✅ Documentation is consistent with codebase!\n')
    console.log(`   Active checks (${checks.length}): ${checks.join(', ')}`)
    process.exit(0)
  } else {
    printDriftCounts(severe)
    if (SHOW_DETAILS) {
      printDriftDetails(severe)
    } else {
      const scope = CHANGE_NAME ? ` --change ${CHANGE_NAME}` : ''
      console.log(`\nDetails hidden. Re-run with --details${scope} to inspect individual drifts.`)
    }
    console.log('\n💡 Fix: update documentation to match code, or create missing code.')
    process.exit(severe.length > 0 ? 1 : 0)
  }
}

main()
