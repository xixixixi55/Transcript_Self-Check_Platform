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
  if (!lastHydratedKey) return true
  const [hydratedCaseId, hydratedRevisionText] = lastHydratedKey.split(':')
  if (hydratedCaseId !== caseId) return true
  const hydratedRevision = Number(hydratedRevisionText)
  return !Number.isFinite(hydratedRevision) || serverDraft.revision > hydratedRevision
}
