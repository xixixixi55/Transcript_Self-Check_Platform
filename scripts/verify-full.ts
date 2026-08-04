import { spawnSync } from 'node:child_process'
import * as path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  buildVerifyCommands,
  parseVerifyScope,
  resolveNpmInvocation,
  runVerifyCommands,
} from './verify-full-utils'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

function runNpm(command: { script: string; args: string[]; cwd: string }): number {
  let invocation
  try {
    invocation = resolveNpmInvocation()
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error))
    return 1
  }

  const result = spawnSync(
    invocation.executable,
    [...invocation.args, 'run', command.script, ...command.args],
    {
      cwd: command.cwd,
      stdio: 'inherit',
    },
  )
  if (result.error) {
    console.error(`Failed to run npm CLI via ${invocation.executable}: ${result.error.message}`)
    return 1
  }
  return result.status ?? 1
}

function formatCommand(command: { script: string; args: string[]; cwd: string }): string {
  const args = command.args.map((arg) => JSON.stringify(arg)).join(' ')
  return `npm run ${command.script}${args ? ` ${args}` : ''} | cwd=${JSON.stringify(command.cwd)}`
}

function main(): number {
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

  return runVerifyCommands(commands, runNpm)
}

process.exit(main())
