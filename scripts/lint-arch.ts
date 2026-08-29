/**
 * lint-arch.ts — 架构约束检查器
 *
 * 检查内容：
 * 1. 依赖方向：确保 import 不违反分层架构
 * 2. 文件大小：推荐目标、评估说明和有界豁免
 * 3. 命名约定：根据项目配置检查文件命名
 *
 * 用法：npx tsx scripts/lint-arch.ts
 * 退出码：0 = 通过，1 = 存在违规
 */

import * as fs from 'node:fs'
import * as path from 'node:path'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// ─── 项目配置（由 harness.config.yaml 生成） ─────────

/** 源码根目录列表（Monorepo 结构） */
const ROOT = path.resolve(__dirname, '..')
const SRC_DIRS = [
  path.resolve(ROOT, 'packages/shared'),
  path.resolve(ROOT, 'packages/frontend/src'),
  path.resolve(ROOT, 'packages/backend/app'),
]

/** 文件大小分档：≤400 推荐，401–600 允许高内聚保留，601–800 需说明。 */
const RECOMMENDED_MAX_LINES = 400
const EXPLANATION_REQUIRED_LINES = 600
const PRINCIPLE_MAX_LINES = 800

/**
 * 600 行以上文件的有界治理说明。超过 maxLines 会重新失败，避免豁免静默扩张。
 * >800 行条目必须说明暂不拆分的明确理由；禁止用 support/helper/pass-through
 * 模块只做行数搬运。
 */
const FILE_SIZE_JUSTIFICATIONS: Record<string, { maxLines: number; reason: string }> = {
  'packages/backend/app/services/template/template_filler_service.py': {
    maxLines: 1100,
    reason: 'Existing Legacy template orchestration remains behavior-frozen until natural renderer and plan boundaries are implemented and verified.',
  },
}

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
  'repository': ['types', 'constants', 'utils', 'repository'],
  'services': ['types', 'constants', 'utils', 'repository', 'services'],
  'controllers': ['types', 'constants', 'services'],
  'routes': ['types', 'constants', 'controllers'],
  // 组合根：app/*.py 负责创建 FastAPI 实例、注册路由、配置中间件。
  // 仅允许应用组装所需的最小依赖集，不得在此层编写业务逻辑。
  'bootstrap': ['types', 'constants', 'routes', 'controllers'],
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

// ─── 项目配置结束 ───────────────────────────────────────────────

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

  // Python 依赖方向检查由 checkAllPythonDeps() 批量处理
  if (filePath.endsWith('.py')) return []

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

// ─── Python 依赖方向检查（基于 AST）──────────────────

/** Python 包名到架构层的映射 */
const PYTHON_LAYER_FROM_MODULE: Record<string, string> = {
  'repository': 'repository',
  'services': 'services',
  'controllers': 'controllers',
  'routes': 'routes',
}

/**
 * 中立模块：纯基础设施，任何架构层均可安全导入。
 *
 * config — 路径常量（纯设置，无 I/O）与简单应用配置存取（硬件设备 JSON CRUD）。
 *          配置存取使用标准库 json/os/uuid，不依赖业务模块。
 *          不包含 archive/pdf 等复杂 I/O 编排逻辑。
 */
const PYTHON_NEUTRAL_MODULES = new Set(['config'])

/**
 * Python 依赖方向检查。
 *
 * 解析 `from ..X.Y import ...` 和 `from .X import ...` 的相对导入，
 * 提取导入目标所在层，与当前文件所在层比较。
 */
function checkAllPythonDeps(pythonFiles: string[], srcDir: string): Violation[] {
  const violations: Violation[] = []
  if (pythonFiles.length === 0) return violations

  let importMap: Record<string, any> = {}
  try {
    const result = execFileSync(
      'python',
      [path.resolve(ROOT, 'scripts/_python_imports.py'), ...pythonFiles],
      { encoding: 'utf-8', maxBuffer: 10 * 1024 * 1024, stdio: ['pipe', 'pipe', 'pipe'] }
    )
    importMap = JSON.parse(result)
  } catch (err: any) {
    console.error('Python AST 导入提取失败:', err.stderr || err.message)
    process.exit(2)
  }

  // 语法错误文件 → 必须报告为违规
  const errors: Array<{ file: string; error: string }> = importMap['__errors__'] || []
  for (const e of errors) {
    violations.push({
      file: path.relative(ROOT, e.file),
      line: 0,
      rule: 'dependency-direction',
      message: `Python 语法错误，无法解析导入: ${e.error}`,
    })
  }
  delete importMap['__errors__']

  for (const [filePath, imports] of Object.entries(importMap)) {
    if (!imports || !Array.isArray(imports) || imports.length === 0) continue
    const impList = imports as Array<{ line: number; level: number; module: string; absolute?: boolean }>

    // app/*.py 作为组合根（bootstrap），可以导入任何 BE 层
    let currentLayer = getLayer(filePath, srcDir)
    if (!currentLayer) {
      const relToSrc = path.relative(srcDir, filePath).replace(/\\/g, '/')
      if (!relToSrc.includes('/')) currentLayer = 'bootstrap'
    }
    if (!currentLayer) continue

    const allowed = ALLOWED_DEPS[currentLayer]
    if (!allowed) continue

    for (const imp of impList) {
      const { line, level, module: modulePath } = imp

      // 绝对导入 (level=0, absolute=true): 模块路径已去除 app. 前缀
      // 相对导入 (level>=1): 模块路径为相对路径
      const topModule = modulePath.split('.')[0]

      let targetLayer: string | null = null
      if (level === 1) {
        targetLayer = currentLayer
      } else if (level === 0 && imp.absolute) {
        // 项目内部绝对导入: topModule 是 app 下的第一层包名
        if (PYTHON_NEUTRAL_MODULES.has(topModule)) continue
        targetLayer = PYTHON_LAYER_FROM_MODULE[topModule] || null
      } else {
        // level >= 2 相对导入
        if (PYTHON_NEUTRAL_MODULES.has(topModule)) continue
        targetLayer = PYTHON_LAYER_FROM_MODULE[topModule] || null
      }
      if (!targetLayer) continue

      if (targetLayer === currentLayer) {
        if (allowed.includes(targetLayer)) continue
        violations.push({
          file: path.relative(ROOT, filePath), line,
          rule: 'dependency-direction',
          message: `Layer "${currentLayer}" MUST NOT import from same layer "${targetLayer}". Allowed: [${allowed.join(', ')}]`,
        })
        continue
      }

      if (BE_LAYERS.has(currentLayer) && FE_LAYERS.has(targetLayer)) {
        violations.push({
          file: path.relative(ROOT, filePath), line,
          rule: 'cross-boundary',
          message: `BE layer "${currentLayer}" MUST NOT import from FE layer "${targetLayer}".`,
        })
        continue
      }

      if (!allowed.includes(targetLayer)) {
        violations.push({
          file: path.relative(ROOT, filePath), line,
          rule: 'dependency-direction',
          message: `Layer "${currentLayer}" MUST NOT import from "${targetLayer}". Allowed: [${allowed.join(', ')}]`,
        })
      }
    }
  }

  return violations
}


function checkFileSize(filePath: string, content: string): Violation[] {
  const lineCount = content.split('\n').length
  const relPath = path.relative(ROOT, filePath)
  if (lineCount <= RECOMMENDED_MAX_LINES) return []
  if (lineCount <= EXPLANATION_REQUIRED_LINES) return []

  const normalizedPath = relPath.replace(/\\/g, '/')
  const justification = FILE_SIZE_JUSTIFICATIONS[normalizedPath]
  if (
    justification
    && justification.reason.trim().length > 0
    && justification.maxLines >= lineCount
  ) return []

  const message = lineCount > PRINCIPLE_MAX_LINES
    ? `File has ${lineCount} lines, exceeds the principle maximum of ${PRINCIPLE_MAX_LINES}. Split along natural responsibility boundaries or register a bounded FILE_SIZE_JUSTIFICATIONS exemption with an explicit reason; never split solely for LOC.`
    : `File has ${lineCount} lines, exceeds ${EXPLANATION_REQUIRED_LINES}. Evaluate natural responsibility boundaries and register a bounded FILE_SIZE_JUSTIFICATIONS explanation when cohesion justifies retaining it; do not split solely for LOC.`
  return [{ file: relPath, line: 0, rule: 'file-size', message }]
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
  const allPythonFiles: string[] = []

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
      if (file.endsWith('.py')) {
        allPythonFiles.push(file)
      }
    }
  }

  // 批量 AST 解析所有 Python 文件的导入依赖
  if (allPythonFiles.length > 0) {
    const beSrcDir = SRC_DIRS.find(d => d.endsWith('app')) || SRC_DIRS[2]
    allViolations.push(...checkAllPythonDeps(allPythonFiles, beSrcDir))
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
