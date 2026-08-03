export interface VerifyScope {
  all: boolean
  change?: string
}

export interface VerifyCommand {
  script: string
  args: string[]
  cwd: string
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
