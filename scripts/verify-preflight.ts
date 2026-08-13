import {
  accessSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  statfsSync,
} from 'node:fs'
import { constants } from 'node:fs'
import * as os from 'node:os'
import * as path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  evaluateVerificationPreflight,
  parseVerificationPreflightConfig,
} from './verification-preflight-utils'

export interface VerificationPreflightResult {
  passed: boolean
  tempRoot: string
  failureTailLines: number
}

export function resolveVerificationTempRoot(
  root: string,
  environment: NodeJS.ProcessEnv = process.env,
  platform: NodeJS.Platform = process.platform,
): string {
  const configured = environment.HARNESS_TEMP_ROOT?.trim()
  if (configured) {
    return platform === 'win32' ? path.win32.resolve(configured) : path.resolve(configured)
  }
  if (platform !== 'win32') return path.resolve(os.tmpdir())

  const projectRoot = path.win32.resolve(root)
  return path.win32.join(path.win32.parse(projectRoot).root, 'harness-temp-root')
}

function canWrite(tempRoot: string): boolean {
  let probePath: string | undefined
  try {
    mkdirSync(tempRoot, { recursive: true })
    accessSync(tempRoot, constants.W_OK)
    probePath = mkdtempSync(path.join(tempRoot, 'harness-preflight-'))
    return true
  } catch {
    return false
  } finally {
    if (probePath) rmSync(probePath, { recursive: true, force: true })
  }
}

function freeSpaceMb(tempRoot: string): number | undefined {
  try {
    const stats = statfsSync(tempRoot)
    return (stats.bavail * stats.bsize) / (1024 * 1024)
  } catch {
    return undefined
  }
}

export function runVerificationPreflight(root: string): VerificationPreflightResult {
  const config = parseVerificationPreflightConfig(
    readFileSync(path.join(root, 'harness.config.yaml'), 'utf8'),
  )
  const tempRoot = resolveVerificationTempRoot(root)
  const checks = evaluateVerificationPreflight({
    tempRoot,
    writable: canWrite(tempRoot),
    freeSpaceMb: freeSpaceMb(tempRoot),
  }, config)
  const failed = checks.filter((check) => !check.passed)

  if (failed.length === 0) {
    console.log(`preflight | PASS | temp=${JSON.stringify(tempRoot)}`)
  } else {
    console.error(`preflight | FAIL | ${failed.length}/${checks.length} checks failed`)
    failed.forEach((check) => console.error(`- ${check.name}: ${check.detail}`))
    console.error('Create a short writable directory on a volume with enough space, then set HARNESS_TEMP_ROOT to it.')
  }

  return {
    passed: failed.length === 0,
    tempRoot,
    failureTailLines: config.failureTailLines,
  }
}

const invokedPath = process.argv[1] ? path.resolve(process.argv[1]) : ''
if (invokedPath === fileURLToPath(import.meta.url)) {
  const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
  process.exit(runVerificationPreflight(root).passed ? 0 : 1)
}
