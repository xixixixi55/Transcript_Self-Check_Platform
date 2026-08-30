import type {
  PlannedVolumeSlot,
  ReconciledVolumeSlots,
  VerifiedVolumeSlot,
  VolumeSlot,
} from '../types'

export function reconcileVolumeSlots(
  previousSlots: readonly VolumeSlot[],
  plannedSlots: readonly PlannedVolumeSlot[],
  planRevision: number,
  createSlotId: (lineageKey: string) => string,
): ReconciledVolumeSlots {
  assertPlanInputs(plannedSlots, planRevision)
  const previousByLineage = new Map(
    previousSlots.filter(slot => slot.status !== 'removed').map(slot => [slot.lineage_key, slot]),
  )
  const activeSlots = plannedSlots
    .map(planned => {
      const previous = previousByLineage.get(planned.lineage_key)
      if (previous) previousByLineage.delete(planned.lineage_key)
      const slotId = previous?.slot_id ?? createSlotId(planned.lineage_key)
      return {
        slot_id: slotId,
        ordinal: planned.ordinal,
        plan_revision: planRevision,
        lineage_key: planned.lineage_key,
        planned_input_bytes: planned.planned_input_bytes,
        status: previous ? 'active' : 'pending',
        disc_mapping: previous?.disc_mapping
          ? { ...previous.disc_mapping, slot_id: slotId }
          : null,
      } satisfies VolumeSlot
    })
    .sort((left, right) => left.ordinal - right.ordinal)
  const removedSlots = [...previousByLineage.values()].map(slot => ({
    ...slot,
    plan_revision: planRevision,
    status: 'removed' as const,
    disc_mapping: null,
  }))
  return { active_slots: activeSlots, removed_slots: removedSlots }
}

export function hasValidUniqueDiscMappings(slots: readonly VolumeSlot[]): boolean {
  const activeSlots = slots.filter(slot => slot.status !== 'removed')
  const discNumbers = activeSlots.map(slot => slot.disc_mapping?.disc_number.trim() ?? '')
  if (discNumbers.some(value => !value)) return false
  const normalized = discNumbers.map(value => value.toLocaleUpperCase('zh-CN'))
  return new Set(normalized).size === normalized.length
    && activeSlots.every(slot => slot.disc_mapping?.confirmation === 'confirmed')
}

export function convergeVolumeSlotsWithManifest(
  slots: readonly VolumeSlot[],
  verifiedSlots: readonly VerifiedVolumeSlot[],
): VolumeSlot[] {
  const activeSlots = slots.filter(slot => slot.status !== 'removed')
  if (!hasValidUniqueDiscMappings(activeSlots) || activeSlots.length !== verifiedSlots.length) {
    throw new Error('MANIFEST_SLOT_MISMATCH')
  }
  const verifiedById = new Map(verifiedSlots.map(slot => [slot.slot_id, slot]))
  if (verifiedById.size !== verifiedSlots.length) throw new Error('MANIFEST_SLOT_MISMATCH')

  return activeSlots.map(slot => {
    const verified = verifiedById.get(slot.slot_id)
    if (
      !verified
      || verified.ordinal !== slot.ordinal
      || verified.disc_number !== slot.disc_mapping?.disc_number
      || !Number.isSafeInteger(verified.output_bytes)
      || verified.output_bytes <= 0
      || !hasValidVerifiedHash(verified)
    ) {
      throw new Error('MANIFEST_SLOT_MISMATCH')
    }
    return { ...slot, status: 'verified' }
  })
}

function hasValidVerifiedHash(slot: VerifiedVolumeSlot): boolean {
  if ('hash_algorithm' in slot) {
    const expectedLength = slot.hash_algorithm === 'md5' ? 32
      : slot.hash_algorithm === 'sha1' ? 40
        : slot.hash_algorithm === 'sha256' ? 64 : 0
    return expectedLength > 0
      && typeof slot.hash_value === 'string'
      && slot.hash_value.length === expectedLength
      && /^[a-f0-9]+$/i.test(slot.hash_value)
  }
  return typeof slot.md5 === 'string' && /^[a-f0-9]{32}$/i.test(slot.md5)
}

function assertPlanInputs(plannedSlots: readonly PlannedVolumeSlot[], planRevision: number): void {
  if (!Number.isSafeInteger(planRevision) || planRevision < 1) throw new Error('INVALID_ARCHIVE_PLAN')
  const lineageKeys = plannedSlots.map(slot => slot.lineage_key)
  const ordinals = plannedSlots.map(slot => slot.ordinal)
  const hasInvalidSlot = plannedSlots.some(slot =>
    !slot.lineage_key
    || !Number.isSafeInteger(slot.ordinal)
    || slot.ordinal < 1
    || !Number.isSafeInteger(slot.planned_input_bytes)
    || slot.planned_input_bytes < 0,
  )
  if (
    hasInvalidSlot
    || new Set(lineageKeys).size !== lineageKeys.length
    || new Set(ordinals).size !== ordinals.length
  ) {
    throw new Error('INVALID_ARCHIVE_PLAN')
  }
}
