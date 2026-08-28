import { existsSync } from 'node:fs'
import * as path from 'node:path'

export interface VerifyScope {
  all: boolean
  change?: string
}

export interface VerifyCommand {
  script: string
  args: string[]
  cwd: string
}

export interface NpmInvocation {
  executable: string
  args: string[]
}

export interface NpmRuntime {
  platform: NodeJS.Platform
  execPath: string
  npmExecPath?: string
  fileExists?: (filePath: string) => boolean
}

export function buildVerificationEnvironment(
  baseEnvironment: NodeJS.ProcessEnv,
  tempRoot: string,
): NodeJS.ProcessEnv {
  return {
    ...baseEnvironment,
    TEMP: tempRoot,
    TMP: tempRoot,
    npm_config_cache: path.join(tempRoot, 'npm-cache'),
  }
}

export function normalizeExitStatus(status: number | null): number {
  if (status === 0) return 0
  return status !== null && status > 0 && status <= 255 ? status : 1
}

/**
 * 将 npm 解析为可直接执行的 Node 入口点。
 * Windows npm.cmd 是 shell 包装器，不能直接传给 spawnSync。
 */
export function resolveNpmInvocation(
  runtime: NpmRuntime = {
    platform: process.platform,
    execPath: process.execPath,
    npmExecPath: process.env.npm_execpath,
  },
): NpmInvocation {
  const fileExists = runtime.fileExists ?? existsSync
  const npmExecPath = runtime.npmExecPath?.trim()
  const runtimePath = runtime.platform === 'win32' ? path.win32 : path.posix

  if (npmExecPath && !npmExecPath.toLowerCase().endsWith('.cmd') && fileExists(npmExecPath)) {
    return { executable: runtime.execPath, args: [npmExecPath] }
  }

  const bundledNpmCli = runtimePath.join(
    runtimePath.dirname(runtime.execPath),
    'node_modules',
    'npm',
    'bin',
    'npm-cli.js',
  )
  if (fileExists(bundledNpmCli)) {
    return { executable: runtime.execPath, args: [bundledNpmCli] }
  }

  if (runtime.platform !== 'win32') return { executable: 'npm', args: [] }

  throw new Error(
    'Unable to locate a directly executable npm CLI on Windows; set npm_execpath to npm-cli.js or install npm with Node.js.',
  )
}

function optionValue(args: string[], name: string): string | undefined {
  const index = args.indexOf(name)
  if (index >= 0) return args[index + 1]

  const prefix = `${name}=`
  const inline = args.find((arg) => arg.startsWith(prefix))
  return inline?.slice(prefix.length)
}

export function parseVerifyScope(args: string[]): VerifyScope {
  const all = args.includes('--all')
  const change = optionValue(args, '--change')?.trim()

  if (all && change) throw new Error('Use either --all or --change <name>, not both.')
  if (!all && !change) throw new Error('A current change is required: use --change <name> or use --all.')

  return all ? { all: true } : { all: false, change }
}

export function buildVerifyCommands(scope: VerifyScope, cwd: string): VerifyCommand[] {
  const steps = [
    'lint:arch',
    'typecheck',
    'test:governance',
    'check:repository-assets',
    'test',
    'build',
  ]
  const commands = steps.map((script) => ({ script, args: [], cwd }))
  const docsScript = scope.all ? 'verify:docs:strict:all' : 'verify:docs:strict'
  const docsArgs = scope.all ? [] : ['--', '--change', scope.change as string]
  return [...commands, { script: docsScript, args: docsArgs, cwd }]
}

export type VerifyCommandRunner = (command: VerifyCommand) => number

export function runVerifyCommands(
  commands: VerifyCommand[],
  runner: VerifyCommandRunner,
): number {
  for (const command of commands) {
    const status = runner(command)
    if (status !== 0) return status
  }
  return 0
}
