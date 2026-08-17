import assert from 'node:assert/strict'
import {
  getManagedAgentToolingFiles,
  getRequiredIncompleteTasks,
  getTaskEntries,
  parseWorkflowLevel,
  validateDeltaSpec,
} from './check-docs-utils'
import {
  buildVerificationEnvironment,
  buildVerifyCommands,
  normalizeExitStatus,
  parseVerifyScope,
  resolveNpmInvocation,
  runVerifyCommands,
} from './verify-full-utils'
import {
  evaluateVerificationPreflight,
  formatDiagnosticTail,
  parseVerificationPreflightConfig,
} from './verification-preflight-utils'
import { resolveVerificationTempRoot } from './verify-preflight'

const content = [
  '- [ ] T1 ordinary task',
  '- [ ] T2 deferred polish [OPTIONAL]',
  '- [ ] T3 waiting for external input [DEFERRED]',
  '- [ ] T4 not applicable [N/A]',
  '- [ ] T5 OPTIONAL in ordinary prose',
  '- [ ] T6 task [OPTIONAL] with trailing prose',
  '- [x] T7 completed task',
].join('\n')

assert.equal(getTaskEntries(content).length, 7)
assert.equal(parseWorkflowLevel('workflow_level: 2\n'), 2)
assert.equal(parseWorkflowLevel('workflow_level: 3\n'), 3)
assert.equal(parseWorkflowLevel('workflow_level: one\n'), undefined)
assert.deepEqual(validateDeltaSpec([
  '## MODIFIED Requirements',
  '### Requirement: REQ-001: Example',
  '#### Scenario: Valid case',
  '- WHEN the condition holds',
  '- THEN the result is stable',
].join('\n')), [])
assert.ok(validateDeltaSpec('## MODIFIED Requirements\n### Requirement: REQ-001').includes('missing Scenario heading'))
assert.deepEqual(
  getRequiredIncompleteTasks(content).map((task) => task.text),
  ['T1 ordinary task', 'T5 OPTIONAL in ordinary prose', 'T6 task [OPTIONAL] with trailing prose'],
)

const lowercaseMarker = '- [ ] T6 optional is not an explicit uppercase exemption'
assert.deepEqual(getRequiredIncompleteTasks(lowercaseMarker).map((task) => task.text), [
  'T6 optional is not an explicit uppercase exemption',
])

assert.deepEqual(getManagedAgentToolingFiles([
  '.agents/commands/harness/apply.md',
  '.claude/commands/harness/apply.md',
  '.agents/skills/harness-apply/SKILL.md',
  '.claude/skills/harness-apply/SKILL.md',
  '.claude/settings.local.json',
  'packages/frontend/src/App.tsx',
]), {
  agentsFiles: ['commands/harness/apply.md', 'skills/harness-apply/SKILL.md'],
  claudeFiles: ['commands/harness/apply.md', 'skills/harness-apply/SKILL.md'],
})

assert.deepEqual(parseVerifyScope(['--change', 'current-change']), {
  all: false,
  change: 'current-change',
})
assert.deepEqual(parseVerifyScope(['--all']), { all: true })
assert.throws(() => parseVerifyScope([]), /current change is required/)
assert.throws(() => parseVerifyScope(['--all', '--change', 'current-change']), /either --all or --change/)

const windowsNode = 'C:\\Program Files\\nodejs\\node.exe'
const windowsNpmCli = 'C:\\Program Files\\nodejs\\node_modules\\npm\\bin\\npm-cli.js'
assert.deepEqual(resolveNpmInvocation({
  platform: 'win32',
  execPath: windowsNode,
  npmExecPath: 'C:\\Program Files\\nodejs\\npm.cmd',
  fileExists: (filePath) => filePath === windowsNpmCli,
}), {
  executable: windowsNode,
  args: [windowsNpmCli],
})
assert.deepEqual(resolveNpmInvocation({
  platform: 'linux',
  execPath: '/usr/bin/node',
  npmExecPath: '/opt/npm/bin/npm-cli.js',
  fileExists: (filePath) => filePath === '/opt/npm/bin/npm-cli.js',
}), {
  executable: '/usr/bin/node',
  args: ['/opt/npm/bin/npm-cli.js'],
})
assert.deepEqual(resolveNpmInvocation({
  platform: 'darwin',
  execPath: '/usr/local/bin/node',
  fileExists: () => false,
}), {
  executable: 'npm',
  args: [],
})
assert.throws(() => resolveNpmInvocation({
  platform: 'win32',
  execPath: 'C:\\node\\node.exe',
  fileExists: () => false,
}), /Unable to locate a directly executable npm CLI/)
assert.deepEqual(buildVerificationEnvironment({ KEEP: 'yes' }, 'D:\\short-temp'), {
  KEEP: 'yes',
  TEMP: 'D:\\short-temp',
  TMP: 'D:\\short-temp',
  npm_config_cache: 'D:\\short-temp\\npm-cache',
})
assert.equal(
  resolveVerificationTempRoot(
    'D:\\workspace\\project', {}, 'win32',
  ),
  'D:\\harness-temp-root',
)
assert.equal(
  resolveVerificationTempRoot(
    'D:\\workspace\\project', { HARNESS_TEMP_ROOT: 'E:\\explicit-temp' }, 'win32',
  ),
  'E:\\explicit-temp',
)
assert.equal(normalizeExitStatus(0), 0)
assert.equal(normalizeExitStatus(17), 17)
assert.equal(normalizeExitStatus(-4055), 1)
assert.equal(normalizeExitStatus(null), 1)

const cwd = 'D:\\中文目录\\with spaces（test）'
const scopedCommands = buildVerifyCommands(
  parseVerifyScope(['--change', '变更 包（test）']),
  cwd,
)
assert.deepEqual(scopedCommands.at(-1), {
  script: 'verify:docs:strict',
  args: ['--', '--change', '变更 包（test）'],
  cwd,
})
assert.ok(scopedCommands.slice(0, -1).every((command) => command.args.length === 0))
assert.ok(scopedCommands.every((command) => command.cwd === cwd))

const visited: string[] = []
const failedStatus = runVerifyCommands(scopedCommands, (command) => {
  visited.push(command.script)
  return command.script === 'test' ? 17 : 0
})
assert.equal(failedStatus, 17)
assert.deepEqual(visited, ['lint:arch', 'typecheck', 'test:governance', 'check:repository-assets', 'test'])

const preflightConfig = parseVerificationPreflightConfig([
  'verification:',
  '  preflight:',
  '    min_free_space_mb: 2048',
  '    max_temp_root_chars: 40',
  '    failure_tail_lines: 3',
].join('\n'))
assert.deepEqual(preflightConfig, {
  minFreeSpaceMb: 2048,
  maxTempRootChars: 40,
  failureTailLines: 3,
})
const failedPreflight = evaluateVerificationPreflight({
  tempRoot: 'C:\\a-very-long-temporary-directory-name-that-exceeds-the-limit',
  writable: false,
  freeSpaceMb: 512,
}, preflightConfig)
assert.deepEqual(
  failedPreflight.filter((check) => !check.passed).map((check) => check.name),
  ['temp-writable', 'temp-path-length', 'temp-free-space'],
)
assert.equal(
  formatDiagnosticTail('\u001b[31mfirst\u001b[0m\nsecond\nthird\nfourth\n', 2),
  'third\nfourth',
)

console.log('check-docs-utils tests passed')
