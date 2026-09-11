import { spawnSync } from 'node:child_process'
import { createRequire } from 'node:module'
import * as path from 'node:path'

const require = createRequire(import.meta.url)
const packageEntryPath = require.resolve('@fission-ai/openspec')
const cliPath = path.join(path.dirname(packageEntryPath), '..', 'bin', 'openspec.js')
const result = spawnSync(
  process.execPath,
  [cliPath, 'validate', '--specs', '--strict', '--no-interactive'],
  {
    stdio: 'inherit',
    env: { ...process.env, OPENSPEC_TELEMETRY: '0' },
  },
)

process.exit(result.status ?? 1)
