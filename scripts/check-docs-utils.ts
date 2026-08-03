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
