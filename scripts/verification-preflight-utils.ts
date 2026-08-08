export interface VerificationPreflightConfig {
  minFreeSpaceMb: number
  maxTempRootChars: number
  failureTailLines: number
}

export interface VerificationPreflightSnapshot {
  tempRoot: string
  writable: boolean
  freeSpaceMb?: number
}

export interface VerificationPreflightCheck {
  name: 'temp-writable' | 'temp-path-length' | 'temp-free-space'
  passed: boolean
  detail: string
}

export const DEFAULT_VERIFICATION_PREFLIGHT_CONFIG: VerificationPreflightConfig = {
  minFreeSpaceMb: 1024,
  maxTempRootChars: 80,
  failureTailLines: 60,
}

function readPositiveInteger(content: string, key: string, fallback: number): number {
  const match = content.match(new RegExp(`^\\s*${key}:\\s*(\\d+)\\s*$`, 'm'))
  if (!match) return fallback
  const value = Number(match[1])
  return Number.isSafeInteger(value) && value > 0 ? value : fallback
}

export function parseVerificationPreflightConfig(content: string): VerificationPreflightConfig {
  return {
    minFreeSpaceMb: readPositiveInteger(
      content,
      'min_free_space_mb',
      DEFAULT_VERIFICATION_PREFLIGHT_CONFIG.minFreeSpaceMb,
    ),
    maxTempRootChars: readPositiveInteger(
      content,
      'max_temp_root_chars',
      DEFAULT_VERIFICATION_PREFLIGHT_CONFIG.maxTempRootChars,
    ),
    failureTailLines: readPositiveInteger(
      content,
      'failure_tail_lines',
      DEFAULT_VERIFICATION_PREFLIGHT_CONFIG.failureTailLines,
    ),
  }
}

export function evaluateVerificationPreflight(
  snapshot: VerificationPreflightSnapshot,
  config: VerificationPreflightConfig,
): VerificationPreflightCheck[] {
  const freeSpaceKnown = snapshot.freeSpaceMb !== undefined
  return [
    {
      name: 'temp-writable',
      passed: snapshot.writable,
      detail: snapshot.writable
        ? `temporary directory is writable: ${snapshot.tempRoot}`
        : `temporary directory is not writable: ${snapshot.tempRoot}`,
    },
    {
      name: 'temp-path-length',
      passed: snapshot.tempRoot.length <= config.maxTempRootChars,
      detail: `temporary path length ${snapshot.tempRoot.length}/${config.maxTempRootChars}: ${snapshot.tempRoot}`,
    },
    {
      name: 'temp-free-space',
      passed: !freeSpaceKnown || (snapshot.freeSpaceMb as number) >= config.minFreeSpaceMb,
      detail: freeSpaceKnown
        ? `temporary volume free space ${Math.floor(snapshot.freeSpaceMb as number)} MB/${config.minFreeSpaceMb} MB`
        : 'temporary volume free space unavailable; check skipped',
    },
  ]
}

export function formatDiagnosticTail(output: string, maxLines: number): string {
  const withoutAnsi = output.replace(/\u001b\[[0-?]*[ -/]*[@-~]/g, '')
  const lines = withoutAnsi.split(/\r?\n/).filter((line) => line.trim().length > 0)
  return lines.slice(-maxLines).join('\n')
}
