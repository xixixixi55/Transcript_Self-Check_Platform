interface DraftIdentity {
  case_id: string
  revision: number
}

export function shouldHydrateServerDraft(
  caseId: string,
  serverDraft: DraftIdentity | null | undefined,
  lastHydratedKey: string | null,
  changeToken: number,
): boolean {
  if (!serverDraft || serverDraft.case_id !== caseId || changeToken > 0) return false
  return `${caseId}:${serverDraft.revision}` !== lastHydratedKey
}
