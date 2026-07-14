/**
 * lint-arch.ts — 架构约束检查器
 *
 * 检查内容：
 * 1. 依赖方向：确保 import 不违反分层架构
 * 2. 文件大小：每个文件不超过配置的行数上限
 * 3. 命名约定：根据项目配置检查文件命名
 *
 * 用法：npx tsx scripts/lint-arch.ts
 * 退出码：0 = 通过，1 = 存在违规
 */

import * as fs from 'node:fs'
import * as path from 'node:path'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// ─── PROJECT CONFIG (generated from harness.config.yaml) ─────────

/** 源码根目录列表（Monorepo 结构） */
const ROOT = path.resolve(__dirname, '..')
const SRC_DIRS = [
  path.resolve(ROOT, 'packages/shared'),
  path.resolve(ROOT, 'packages/frontend/src'),
  path.resolve(ROOT, 'packages/backend/app'),
]

/** 文件大小上限 */
const MAX_LINES = 250

/**
 * 层级定义（数字越大层级越高，低层不能引用高层）
 * 层号采用分段编号：Shared(0-2) / FE(10-12) / BE(20-23)
 */
const LAYER_MAP: Record<string, number> = {
  'types': 0,
  'constants': 1,
  'utils': 2,
  'hooks': 10,
  'components': 11,
  'pages': 12,
  'repository': 20,
  'services': 21,
  'controllers': 22,
  'routes': 23,
}

/**
 * 每层允许引用的层级（白名单）
 * key = 引用方所在层, value = 允许被引用的层列表
 */
const ALLOWED_DEPS: Record<string, string[]> = {
  'types': [],
  'constants': ['types'],
  'utils': ['types', 'constants'],
  'hooks': ['types', 'constants', 'utils', 'hooks'],
  'components': ['types', 'constants', 'hooks', 'components'],
  'pages': ['types', 'constants', 'hooks', 'components'],
  'repository': ['types', 'constants', 'utils'],
  'services': ['types', 'constants', 'utils', 'repository'],
  'controllers': ['types', 'constants', 'services'],
  'routes': ['types', 'constants', 'controllers'],
}

/** 前端层与后端层禁止互相引用（跨边界检查） */
const FE_LAYERS = new Set(['hooks', 'components', 'pages'])
const BE_LAYERS = new Set(['repository', 'services', 'controllers', 'routes'])
const SHARED_LAYERS = new Set(['types', 'constants', 'utils'])

/**
 * 命名约定规则
 */
interface NamingRule {
  dirPrefix: string
  extension: string
  pattern: RegExp
  ruleName: string
  example: string
  exclude?: string[]
}

const NAMING_RULES: NamingRule[] = [
  {
    dirPrefix: 'components/',
    extension: '.tsx',
    pattern: /^[A-Z][a-zA-Z0-9]*$/,
    ruleName: 'PascalCase',
    example: 'RecordEditor.tsx',
    exclude: ['index'],
  },
  {
    dirPrefix: 'hooks/',
    extension: '.ts',
    pattern: /^use[A-Z][a-zA-Z0-9]*$/,
    ruleName: 'use-prefix',
    example: 'useRecordGenerate.ts',
    exclude: ['index'],
  },
]

/** Python 命名规则（仅作文件大小检查，不检查依赖方向） */
const PYTHON_NAMING_RULES: NamingRule[] = [
  {
    dirPrefix: 'controllers/',
    extension: '.py',
    pattern: /^[a-z][a-z0-9_]*_controller$/,
    ruleName: 'snake_case_controller',
    example: 'record_controller.py',
    exclude: ['__init__'],
  },
  {
    dirPrefix: 'services/',
    extension: '.py',
    pattern: /^[a-z][a-z0-9_]*_service$/,
    ruleName: 'snake_case_service',
    example: 'record_service.py',
    exclude: ['__init__'],
  },
]

const PATH_ALIASES: Record<string, string> = {
  '@biji/shared/': 'packages/shared/',
}

// ─── END PROJECT CONFIG ──────────────────────────────────────────

interface Violation {
  file: string
  line: number
  rule: string
  message: string
}

// ─── 层级解析 ───────────────────────────────────────

function getLayer(filePath: string, srcDir: string): string | null {
  const relative = path.relative(srcDir, filePath).replace(/\\/g, '/')
  const layers = Object.keys(LAYER_MAP).sort((a, b) => b.length - a.length)
  for (const layer of layers) {
    if (relative.startsWith(layer + '/') || relative === layer) {
      return layer
    }
  }
  return null
}

function getLayerDir(layer: string): string | null {
  for (const srcDir of SRC_DIRS) {
    const candidate = path.join(srcDir, layer)
    if (fs.existsSync(candidate)) return candidate
  }
  return null
}

function resolveImportLayer(importPath: string, currentFile: string, srcDir: string): string | null {
  for (const [alias, replacement] of Object.entries(PATH_ALIASES)) {
    if (importPath.startsWith(alias)) {
      const resolved = importPath.replace(alias, replacement)
      const layers = Object.keys(LAYER_MAP).sort((a, b) => b.length - a.length)
      for (const layer of layers) {
        if (resolved.startsWith(layer + '/') || resolved === layer) {
          return layer
        }
      }
    }
  }

  if (importPath.startsWith('.')) {
    const dir = path.dirname(currentFile)
    const resolved = path.resolve(dir, importPath)
    return getLayer(resolved, srcDir)
  }

  return null
}

// ─── 检查器 ───────────────────────────────────────

function checkDependencyDirection(filePath: string, content: string, srcDir: string): Violation[] {
  const violations: Violation[] = []
  const currentLayer = getLayer(filePath, srcDir)
  if (!currentLayer) return violations

  // Python 文件只检查文件大小和命名，不检查 import 依赖方向
  if (filePath.endsWith('.py')) return violations

  const allowed = ALLOWED_DEPS[currentLayer]
  if (!allowed) return violations

  const lines = content.split('\n')
  lines.forEach((line, index) => {
    const match = line.match(/(?:import|from)\s+['"]([^'"]+)['"]/)
    if (!match) return

    const importPath = match[1]
    const targetLayer = resolveImportLayer(importPath, filePath, srcDir)
    if (!targetLayer) return
    if (targetLayer === currentLayer) return

    // 跨边界检查：前端和后端层禁止互相引用
    if (FE_LAYERS.has(currentLayer) && BE_LAYERS.has(targetLayer)) {
      violations.push({
        file: path.relative(ROOT, filePath),
        line: index + 1,
        rule: 'cross-boundary',
        message: `FE layer "${currentLayer}" MUST NOT import from BE layer "${targetLayer}". Communication via API only.`,
      })
      return
    }
    if (BE_LAYERS.has(currentLayer) && FE_LAYERS.has(targetLayer)) {
      violations.push({
        file: path.relative(ROOT, filePath),
        line: index + 1,
        rule: 'cross-boundary',
        message: `BE layer "${currentLayer}" MUST NOT import from FE layer "${targetLayer}". Communication via API only.`,
      })
      return
    }

    if (!allowed.includes(targetLayer)) {
      violations.push({
        file: path.relative(ROOT, filePath),
        line: index + 1,
        rule: 'dependency-direction',
        message: `Layer "${currentLayer}" MUST NOT import from "${targetLayer}". Allowed: [${allowed.join(', ')}]`,
      })
    }
  })

  return violations
}

function checkFileSize(filePath: string, content: string): Violation[] {
  const lineCount = content.split('\n').length
  if (lineCount > MAX_LINES) {
    return [{
      file: path.relative(ROOT, filePath),
      line: 0,
      rule: 'file-size',
      message: `File has ${lineCount} lines, exceeds maximum of ${MAX_LINES} lines. MUST split.`,
    }]
  }
  return []
}

function checkNamingConvention(filePath: string, srcDir: string): Violation[] {
  const violations: Violation[] = []
  const relative = path.relative(srcDir, filePath).replace(/\\/g, '/')
  const fileName = path.basename(filePath, path.extname(filePath))
  const ext = path.extname(filePath)

  // 跳过测试文件（.test. / .spec.）
  if (fileName.includes('.test') || fileName.includes('.spec')) return violations

  const rules = filePath.endsWith('.py') ? PYTHON_NAMING_RULES : NAMING_RULES

  for (const rule of rules) {
    if (!relative.startsWith(rule.dirPrefix)) continue
    if (ext !== rule.extension) continue
    if (rule.exclude?.includes(fileName)) continue

    if (!rule.pattern.test(fileName)) {
      violations.push({
        file: path.relative(ROOT, filePath),
        line: 0,
        rule: 'naming-convention',
        message: `File "${fileName}${ext}" MUST follow ${rule.ruleName} (e.g., "${rule.example}")`,
      })
    }
  }

  return violations
}

// ─── 主流程 ───────────────────────────────────────

function walkDir(dir: string, extensions: string[]): string[] {
  const results: string[] = []
  if (!fs.existsSync(dir)) return results

  const entries = fs.readdirSync(dir, { withFileTypes: true })
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name)
    if (entry.isDirectory()) {
      // 跳过 node_modules, dist, __pycache__, .venv
      if (['node_modules', 'dist', '__pycache__', '.venv', '.git'].includes(entry.name)) continue
      results.push(...walkDir(fullPath, extensions))
    } else if (extensions.some(ext => entry.name.endsWith(ext))) {
      results.push(fullPath)
    }
  }
  return results
}

function main() {
  console.log('🔍 Architecture Lint — checking constraints...\n')

  const SOURCE_EXTENSIONS = ['.ts', '.tsx', '.py']
  const allViolations: Violation[] = []

  for (const srcDir of SRC_DIRS) {
    const ext = srcDir.endsWith('app') ? ['.py'] : ['.ts', '.tsx']
    const files = walkDir(srcDir, ext)
    console.log(`  Scanning ${path.relative(ROOT, srcDir)}/ (${files.length} files)...`)

    for (const file of files) {
      const content = fs.readFileSync(file, 'utf-8')
      allViolations.push(
        ...checkDependencyDirection(file, content, srcDir),
        ...checkFileSize(file, content),
        ...checkNamingConvention(file, srcDir),
      )
    }
  }

  console.log('')

  if (allViolations.length === 0) {
    console.log('✅ All architecture constraints passed!\n')
    console.log('   Rules: dependency-direction, cross-boundary, file-size, naming-convention')
    process.exit(0)
  } else {
    console.log(`❌ Found ${allViolations.length} violation(s):\n`)
    for (const v of allViolations) {
      const location = v.line > 0 ? `:${v.line}` : ''
      console.log(`  ${v.file}${location}`)
      console.log(`    [${v.rule}] ${v.message}\n`)
    }
    process.exit(1)
  }
}

main()
