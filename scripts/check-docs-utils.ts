export interface TaskEntry {
  lineNumber: number
  checked: boolean
  text: string
  exemption?: 'OPTIONAL' | 'DEFERRED' | 'N/A'
}

const TASK_LINE_PATTERN = /^\s*-\s*\[([ xX])\]\s+(.+?)\s*$/
const EXEMPTION_PATTERN = /\[(OPTIONAL|DEFERRED|N\/A)\]\s*$/

/** 解析检查清单条目，不根据任务标题或源文件推断含义。 */
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

/** 普通未勾选任务为必选项；显式大写标记可豁免。 */
export function getRequiredIncompleteTasks(content: string): TaskEntry[] {
  return getTaskEntries(content).filter((entry) => !entry.checked && !entry.exemption)
}

/** 仅从已完成且适用的任务条目中提取文件引用。 */
export function getCompletedTaskFileReferences(content: string): string[] {
  const completedTasks = getTaskEntries(content.replace(/```[\s\S]*?```/g, ''))
    .filter((entry) => entry.checked && !entry.exemption)

  return completedTasks
    .flatMap((entry) => entry.text.match(/`[^`]+\.[a-z]+`/g) || [])
    .map((ref) => ref.replace(/`/g, ''))
}

export type WorkflowLevel = 2 | 3
export type SpecSyncStatus = 'pending' | 'partial' | 'reconciled'

/** 从 tasks.md 元数据头部读取稳定的顶层标量。 */
export function getWorkflowMetadata(content: string, key: string): string | undefined {
  const pattern = new RegExp(`^${key}:\\s*([^\\r\\n#]+?)\\s*$`, 'mi')
  return content.match(pattern)?.[1]?.trim()
}

/** 解析持久化的工作流级别；绝不从其他工件推断。 */
export function parseWorkflowLevel(content: string): WorkflowLevel | undefined {
  const value = getWorkflowMetadata(content, 'workflow_level')
  if (value === '2' || value === '3') return Number(value) as WorkflowLevel
  return undefined
}

/** 只验证 OpenSpec 增量的结构契约，不验证其语义。 */
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

/** 在 LF 和 CRLF 内容中一致地统计逻辑文本行。 */
export function countTextLines(content: string): number {
  if (content.length === 0) return 0
  return content.replaceAll('\r\n', '\n').split('\n').length
}

/** 仅在文档超过预算时返回实际行数。 */
export function getLineBudgetOverflow(content: string, maxLines: number): number | undefined {
  const lineCount = countTextLines(content)
  return lineCount > maxLines ? lineCount : undefined
}

/** 让高频 Harness 命令充当渐进式路由器，而非预加载文档。 */
export function validateProgressiveContextCommand(content: string): string[] {
  const errors: string[] = []
  if (!/<!--\s*context-loading:\s*progressive\s*-->/i.test(content)) {
    errors.push('missing progressive context marker')
  }
  if (!/(?:渐进式|按需)(?:上下文|读取|加载)/i.test(content)) {
    errors.push('missing progressive loading instructions')
  }
  if (/MUST\s*在开始前阅读|前置读取[^\n]*(?:MUST|必须)/i.test(content)) {
    errors.push('contains unconditional pre-read instruction')
  }
  if (!/AGENTS\.md/i.test(content)) {
    errors.push('missing AGENTS.md policy source')
  }
  return errors
}

export interface ManagedAgentToolingFiles {
  agentsFiles: string[]
  claudeFiles: string[]
}

/** 按提供方镜像根目录对 Git 管理的命令/Skill 文件分组。 */
export function getManagedAgentToolingFiles(files: string[]): ManagedAgentToolingFiles {
  const agentsFiles = new Set<string>()
  const claudeFiles = new Set<string>()

  for (const file of files) {
    const normalized = file.replaceAll('\\', '/')
    for (const [prefix, target] of [
      ['.agents/', agentsFiles],
      ['.claude/', claudeFiles],
    ] as const) {
      if (!normalized.startsWith(prefix)) continue
      const relativeFile = normalized.slice(prefix.length)
      if (relativeFile.startsWith('commands/') || relativeFile.startsWith('skills/')) {
        target.add(relativeFile)
      }
    }
  }

  return {
    agentsFiles: [...agentsFiles].sort(),
    claudeFiles: [...claudeFiles].sort(),
  }
}
