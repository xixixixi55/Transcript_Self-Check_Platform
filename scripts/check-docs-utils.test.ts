import assert from 'node:assert/strict'
import { getRequiredIncompleteTasks, getTaskEntries } from './check-docs-utils'
import {
  buildVerifyCommands,
  parseVerifyScope,
  runVerifyCommands,
} from './verify-full-utils'

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
assert.deepEqual(
  getRequiredIncompleteTasks(content).map((task) => task.text),
  ['T1 ordinary task', 'T5 OPTIONAL in ordinary prose', 'T6 task [OPTIONAL] with trailing prose'],
)

const lowercaseMarker = '- [ ] T6 optional is not an explicit uppercase exemption'
assert.deepEqual(getRequiredIncompleteTasks(lowercaseMarker).map((task) => task.text), [
  'T6 optional is not an explicit uppercase exemption',
])

assert.deepEqual(parseVerifyScope(['--change', 'current-change']), {
  all: false,
  change: 'current-change',
})
assert.deepEqual(parseVerifyScope(['--all']), { all: true })
assert.throws(() => parseVerifyScope([]), /current change is required/)
assert.throws(() => parseVerifyScope(['--all', '--change', 'current-change']), /either --all or --change/)

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

console.log('check-docs-utils tests passed')
