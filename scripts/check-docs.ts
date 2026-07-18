/**
 * check-docs.ts — 文档与代码一致性检查器
 *
 * 检查内容：
 * 1.  [E-A1] 目录结构：directory.md vs 实际文件系统
 * 2.  [补充] npm 命令：AGENTS.md 声明 vs package.json
 * 3.  [补充] tasks.md 文件引用 vs 实际存在性                  [strict]
 * 4.  [补充] tasks.md 完成状态 vs 源码文件存在性               [strict]
 * 5.  [补充] specs 能力目录 vs directory.md/AGENTS.md 中列出的能力名 [strict]
 * 6.  [E-A2] [按需] data-model.md 接口字段 vs 类型定义文件实际字段
 * 7.  [补充] AGENTS.md 行数限制（默认模式：仅警告）
 * 8.  [E-A3] 文档链接有效性
 * 9.  [E-A4] OpenSpec 版本一致性                              [strict]
 * 10. [E-A5] TEMPLATE_CANDIDATE 积压统计                      [strict]
 * 11. [E-A6] 迭代记录教训反哺完整性                           [strict]
 *
 * 用法：
 *   npx tsx scripts/check-docs.ts             默认模式（低噪音检查）
 *   npx tsx scripts/check-docs.ts --strict    严格模式（全部检查）
 * 退出码：0 = 通过，1 = 存在偏差
 */

import * as fs from 'node:fs'
import * as path from 'node:path'
import { fileURLToPath } from 'node:url'

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
  'dev', 'build', 'lint:arch', 'typecheck', 'verify', 'test', 'check-docs', 'pre-commit',
]

/** 期望的源码目录（相对于各 SRC_ROOT，key 为 SRC_ROOT 索引） */
const EXPECTED_DIRS: Record<number, string[]> = {
  0: ['types', 'constants', 'utils', '__tests__'],              // packages/shared
  1: ['hooks', 'components', 'pages', '__tests__'],             // packages/frontend/src
  2: ['repository', 'services', 'controllers', 'routes', 'data'], // packages/backend/app
}

// 默认模式：超出仅警告；严格模式：作为错误阻断
const AGENTS_MAX_LINES = 200

/** 数据模型 spec 路径 */
const DATA_MODEL_MD = path.join(OPENSPEC_DIR, 'specs', 'data-model.md')

/** 类型定义目录 */
const TYPES_DIR = path.join(ROOT, 'packages/shared/types')

// ─── MODE ──────────────────────────────────────────────────────

const STRICT_MODE = process.argv.includes('--strict')

// ─── END PROJECT CONFIG ──────────────────────────────────────────

type DriftType =
  | 'missing-in-code' | 'missing-in-docs' | 'command-missing'
  | 'task-status-stale' | 'spec-not-listed' | 'file-not-in-tree'
  | 'type-drift' | 'broken-link' | 'version-mismatch'
  | 'template-candidate-backlog' | 'lesson-not-fed-back'
  | 'agents-size-exceeded'

interface Drift { type: DriftType; message: string }

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

// ─── Check 3: tasks.md 文件引用 ─────────────

function getActiveTasksContents(): string[] {
  const changesDir = path.join(OPENSPEC_DIR, 'changes')
  if (!fs.existsSync(changesDir)) return []
  const contents: string[] = []
  for (const entry of fs.readdirSync(changesDir, { withFileTypes: true })) {
    if (!entry.isDirectory() || entry.name === 'archive') continue
    const tasksPath = path.join(changesDir, entry.name, 'tasks.md')
    const content = readFileIfExists(tasksPath)
    if (content) contents.push(content)
  }
  return contents
}

function checkTaskFiles(): Drift[] {
  const drifts: Drift[] = []
  for (const content of getActiveTasksContents()) {
    const withoutCodeBlocks = content.replace(/```[\s\S]*?```/g, '')
    const fileRefs = withoutCodeBlocks.match(/`[^`]+\.[a-z]+`/g) || []
    for (const ref of fileRefs) {
      const filePath = ref.replace(/`/g, '')
      if (filePath.includes('*') || filePath.includes('<')) continue
      if (filePath.includes('/') && !fs.existsSync(path.join(ROOT, filePath)))
        drifts.push({ type: 'missing-in-code', message: `tasks.md references "${filePath}" but file does not exist` })
    }
  }
  return drifts
}

// ─── Check 4: tasks.md 完成状态 ─────────────

function checkTaskCompletion(): Drift[] {
  const drifts: Drift[] = []
  for (const content of getActiveTasksContents()) {
    for (const line of content.split('\n')) {
      const m = line.match(/^- \[ \] (T\d+).*`([^`]+\.[a-z]+)`/)
      if (!m) continue
      if (fs.existsSync(path.join(ROOT, m[2])))
        drifts.push({ type: 'task-status-stale', message: `${m[1]} marked [ ] but "${m[2]}" exists — forgot [x]?` })
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
  const lines = content.split('\n').length
  if (lines > AGENTS_MAX_LINES) {
    return [{
      type: 'agents-size-exceeded',
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
  const modeLabel = STRICT_MODE ? 'strict (all checks)' : 'quick (low-noise checks)'
  console.log(`🔍 Documentation Drift Check — mode: ${modeLabel}\n`)

  // Default mode: core checks only
  const allDrifts: Drift[] = [
    ...checkDirectoryStructure(),          // E-A1
    ...checkCommands(),                    // npm commands
    ...checkDataModelConsistency(),        // E-A2
    ...checkAgentsSize(),                  // AGENTS.md size (warn in default, error in strict)
    ...checkDocLinks(),                    // E-A3
  ]

  const checks = [
    'E-A1:directory-structure', 'npm-commands',
    'E-A2:data-model-consistency', 'agents-md-size', 'E-A3:doc-links',
  ]

  // Strict mode: add governance checks
  if (STRICT_MODE) {
    allDrifts.push(
      ...checkTaskFiles(),
      ...checkTaskCompletion(),
      ...checkSpecsListed(),
      ...checkOpenSpecVersion(),
      ...checkTemplateCandidateBacklog(),
      ...checkLessonFeedback(),
    )
    checks.push(
      'task-file-refs', 'task-completion', 'specs-listed',
      'E-A4:openspec-version', 'E-A5:template-candidate-backlog', 'E-A6:lesson-feedback',
    )
  }

  // Separate errors from warnings
  const errors = allDrifts.filter(d => d.type !== 'agents-size-exceeded')
  const warnings = allDrifts.filter(d => d.type === 'agents-size-exceeded')

  // In default mode, AGENTS.md size is a warning (don't fail)
  if (!STRICT_MODE && warnings.length > 0) {
    for (const w of warnings) console.log(`  ⚠️  [${w.type}] ${w.message}`)
  }

  if (errors.length === 0 && (STRICT_MODE || warnings.length === 0)) {
    console.log('✅ Documentation is consistent with codebase!\n')
    console.log(`   Active checks (${checks.length}): ${checks.join(', ')}`)
    process.exit(0)
  } else {
    const severe = STRICT_MODE ? [...errors, ...warnings] : errors
    if (severe.length > 0) {
      console.log(`⚠️  Found ${severe.length} drift(s):\n`)
      for (const d of severe) console.log(`  [${d.type}] ${d.message}`)
      console.log('\n💡 Fix: update documentation to match code, or create missing code.')
    }
    process.exit(severe.length > 0 ? 1 : 0)
  }
}

main()
