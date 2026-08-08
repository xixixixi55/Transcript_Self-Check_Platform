import { spawn } from 'node:child_process'
import {
  createWriteStream,
  mkdtempSync,
  rmSync,
} from 'node:fs'
import * as path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  buildVerificationEnvironment,
  buildVerifyCommands,
  normalizeExitStatus,
  parseVerifyScope,
  resolveNpmInvocation,
} from './verify-full-utils'
import { formatDiagnosticTail } from './verification-preflight-utils'
import { runVerificationPreflight } from './verify-preflight'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

interface CommandResult {
  status: number
  output: string
  error?: string
}

function runNpm(
  command: { script: string; args: string[]; cwd: string },
  logPath: string,
  tempRoot: string,
): Promise<CommandResult> {
  let invocation
  try {
    invocation = resolveNpmInvocation()
  } catch (error) {
    return Promise.resolve({
      status: 1,
      output: '',
      error: error instanceof Error ? error.message : String(error),
    })
  }

  return new Promise((resolve) => {
    const log = createWriteStream(logPath, { encoding: 'utf8' })
    const child = spawn(
      invocation.executable,
      [...invocation.args, 'run', command.script, ...command.args],
      {
        cwd: command.cwd,
        stdio: ['ignore', 'pipe', 'pipe'],
        env: buildVerificationEnvironment(process.env, tempRoot),
      },
    )
    let output = ''
    let settled = false
    const finish = (result: CommandResult) => {
      if (settled) return
      settled = true
      log.end(() => resolve(result))
    }
    const collect = (chunk: Buffer) => {
      const text = chunk.toString('utf8')
      output = `${output}${text}`.slice(-256_000)
      log.write(chunk)
    }
    child.stdout.on('data', collect)
    child.stderr.on('data', collect)
    child.on('error', (error) => {
      finish({ status: 1, output, error: error.message })
    })
    child.on('close', (status) => {
      finish({ status: normalizeExitStatus(status), output })
    })
  })
}

function formatCommand(command: { script: string; args: string[]; cwd: string }): string {
  const args = command.args.map((arg) => JSON.stringify(arg)).join(' ')
  return `npm run ${command.script}${args ? ` ${args}` : ''} | cwd=${JSON.stringify(command.cwd)}`
}

async function main(): Promise<number> {
  let scope: ReturnType<typeof parseVerifyScope>
  try {
    scope = parseVerifyScope(process.argv.slice(2))
  } catch (error) {
    console.error(`verify:full scope error: ${error instanceof Error ? error.message : String(error)}`)
    console.error('Usage: npm run verify:full -- --change <name>')
    console.error('       npm run verify:full:all')
    return 2
  }

  const commands = buildVerifyCommands(scope, ROOT)
  if (process.argv.includes('--dry-run')) {
    const scopeLabel = scope.all ? 'all-active-changes' : `change:${scope.change}`
    console.log(`verify:full dry run | scope=${scopeLabel}`)
    commands.forEach((command, index) => console.log(`${index + 1}. ${formatCommand(command)}`))
    return 0
  }

  const preflight = runVerificationPreflight(ROOT)
  if (!preflight.passed) return 1

  const logRoot = mkdtempSync(path.join(preflight.tempRoot, 'harness-verify-'))
  for (const [index, command] of commands.entries()) {
    const startedAt = Date.now()
    const safeName = command.script.replace(/[^a-z0-9_-]+/gi, '-')
    const logPath = path.join(logRoot, `${String(index + 1).padStart(2, '0')}-${safeName}.log`)
    const result = await runNpm(command, logPath, preflight.tempRoot)
    const durationSeconds = ((Date.now() - startedAt) / 1000).toFixed(1)
    if (result.status === 0) {
      console.log(`${command.script} | PASS | ${durationSeconds}s`)
      rmSync(logPath, { force: true })
      continue
    }

    console.error(`${command.script} | FAIL | exit=${result.status} | ${durationSeconds}s`)
    if (result.error) console.error(result.error)
    const diagnostic = formatDiagnosticTail(result.output, preflight.failureTailLines)
    if (diagnostic) console.error(`--- diagnostic tail ---\n${diagnostic}`)
    console.error(`full log: ${logPath}`)
    return result.status
  }

  rmSync(logRoot, { recursive: true, force: true })
  return 0
}

main()
  .then((status) => process.exit(status))
  .catch((error) => {
    console.error(error instanceof Error ? error.message : String(error))
    process.exit(1)
  })
