export interface TaskEntry {
  lineNumber: number
  checked: boolean
  text: string
  exemption?: 'OPTIONAL' | 'DEFERRED' | 'N/A'
}

const TASK_LINE_PATTERN = /^\s*-\s*\[([ xX])\]\s+(.+?)\s*$/
const EXEMPTION_PATTERN = /\[(OPTIONAL|DEFERRED|N\/A)\]\s*$/

/** Parse checklist entries without inferring meaning from task titles or source files. */
export function getTaskEntries(content: string): TaskEntry[] {
  return content.split('\n').flatMap((line, index) => {
    const match = line.match(TASK_LINE_PATTERN)
    if (!match) return []

    const text = match[2]
    const exemption = text.match(EXEMPTION_PATTERN)?.[1] as TaskEntry['exemption'] | undefined
    return [{
      lineNumber: index + 1,
      checked: match[1].toLowerCase() === 'x',
      text,
      exemption,
    }]
  })
}

/** Ordinary unchecked tasks are required; explicit uppercase markers exempt them. */
export function getRequiredIncompleteTasks(content: string): TaskEntry[] {
  return getTaskEntries(content).filter((entry) => !entry.checked && !entry.exemption)
}

/** Extract file references from completed task entries only. */
export function getCompletedTaskFileReferences(content: string): string[] {
  const completedTaskLines = content
    .replace(/```[\s\S]*?```/g, '')
    .split('\n')
    .filter((line) => /^\s*-\s*\[[xX]\]/.test(line))

  return completedTaskLines
    .flatMap((line) => line.match(/`[^`]+\.[a-z]+`/g) || [])
    .map((ref) => ref.replace(/`/g, ''))
}

export type WorkflowLevel = 2 | 3
export type SpecSyncStatus = 'pending' | 'partial' | 'reconciled'

/** Read a stable top-level scalar from the metadata header in tasks.md. */
export function getWorkflowMetadata(content: string, key: string): string | undefined {
  const pattern = new RegExp(`^${key}:\\s*([^\\r\\n#]+?)\\s*$`, 'mi')
  return content.match(pattern)?.[1]?.trim()
}

/** Parse the persisted workflow level; never infer it from other artifacts. */
export function parseWorkflowLevel(content: string): WorkflowLevel | undefined {
  const value = getWorkflowMetadata(content, 'workflow_level')
  if (value === '2' || value === '3') return Number(value) as WorkflowLevel
  return undefined
}

/** Validate only the structural contract of an OpenSpec delta, not its semantics. */
export function validateDeltaSpec(content: string): string[] {
  const errors: string[] = []
  const sections = [...content.matchAll(/^##\s+(ADDED|MODIFIED|REMOVED|RENAMED)(?:\s+Requirements?|\s*:)/gim)]
    .map((match) => match[1].toUpperCase())

  if (sections.length === 0) errors.push('missing ADDED/MODIFIED/REMOVED/RENAMED section')

  const hasRequirement = /^###\s+(?:Requirement:\s*.+|(?:REQ|CAP)[-_][\w-]+.*)$/im.test(content)
  if (!hasRequirement && sections.some((section) => section !== 'RENAMED')) {
    errors.push('missing Requirement heading')
  }

  const needsScenario = sections.some((section) => section === 'ADDED' || section === 'MODIFIED')
  if (needsScenario) {
    if (!/(?:^#{2,4}\s*Scenario:\s*.+|^\*\*Scenario:\s*.+)/im.test(content)) {
      errors.push('missing Scenario heading')
    }
    if (!/\bWHEN\b/i.test(content)) errors.push('missing WHEN clause')
    if (!/\bTHEN\b/i.test(content)) errors.push('missing THEN clause')
  }

  return errors
}
