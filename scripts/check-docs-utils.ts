/** Extract file references from completed task entries only. */
export function getCompletedTaskFileReferences(content: string): string[] {
  const completedTaskLines = content
    .replace(/```[\s\S]*?```/g, '')
    .split('\n')
    .filter((line) => /^-\s*\[[xX]\]/.test(line))

  return completedTaskLines
    .flatMap((line) => line.match(/`[^`]+\.[a-z]+`/g) || [])
    .map((ref) => ref.replace(/`/g, ''))
}
