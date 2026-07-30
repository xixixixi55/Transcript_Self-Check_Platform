import { describe, expect, it } from 'vitest'
import type { VolumeSlot } from '@biji/shared/types'
import {
  convergeVolumeSlotsWithManifest,
  hasValidUniqueDiscMappings,
  reconcileVolumeSlots,
} from '@biji/shared/utils'

function existingSlot(overrides: Partial<VolumeSlot> = {}): VolumeSlot {
  return {
    slot_id: 'slot-SYNTHETIC-A',
    ordinal: 1,
    plan_revision: 1,
    lineage_key: 'lineage-SYNTHETIC-A',
    planned_input_bytes: 4_000,
    status: 'active',
    disc_mapping: {
      slot_id: 'slot-SYNTHETIC-A',
      disc_number: 'TEST20260730-001',
      disc_date: '2026-07-30',
      source: 'user',
      confirmation: 'confirmed',
    },
    ...overrides,
  }
}

describe('archive volume slot pure rules', () => {
  it('preserves stable slots and confirmed mappings across replan', () => {
    const result = reconcileVolumeSlots(
      [existingSlot(), existingSlot({
        slot_id: 'slot-SYNTHETIC-REMOVED',
        ordinal: 2,
        lineage_key: 'lineage-SYNTHETIC-REMOVED',
        disc_mapping: null,
      })],
      [
        { ordinal: 1, lineage_key: 'lineage-SYNTHETIC-A', planned_input_bytes: 4_500 },
        { ordinal: 2, lineage_key: 'lineage-SYNTHETIC-NEW', planned_input_bytes: 2_000 },
      ],
      2,
      lineage => `slot-created-${lineage}`,
    )
    expect(result.active_slots[0]).toMatchObject({
      slot_id: 'slot-SYNTHETIC-A',
      plan_revision: 2,
      planned_input_bytes: 4_500,
      status: 'active',
      disc_mapping: { disc_number: 'TEST20260730-001' },
    })
    expect(result.active_slots[1]).toMatchObject({
      slot_id: 'slot-created-lineage-SYNTHETIC-NEW',
      status: 'pending',
      disc_mapping: null,
    })
    expect(result.removed_slots).toEqual([
      expect.objectContaining({ slot_id: 'slot-SYNTHETIC-REMOVED', status: 'removed', disc_mapping: null }),
    ])
  })

  it('requires non-empty unique confirmed disc mappings', () => {
    const first = existingSlot()
    const duplicate = existingSlot({
      slot_id: 'slot-SYNTHETIC-B',
      ordinal: 2,
      lineage_key: 'lineage-SYNTHETIC-B',
      disc_mapping: {
        ...first.disc_mapping!,
        slot_id: 'slot-SYNTHETIC-B',
        disc_number: 'test20260730-001',
      },
    })
    expect(hasValidUniqueDiscMappings([first])).toBe(true)
    expect(hasValidUniqueDiscMappings([first, duplicate])).toBe(false)
    expect(hasValidUniqueDiscMappings([{ ...first, disc_mapping: null }])).toBe(false)
  })

  it('converges only complete verified Manifest slots', () => {
    const slot = existingSlot()
    expect(convergeVolumeSlotsWithManifest([slot], [{
      slot_id: slot.slot_id,
      ordinal: slot.ordinal,
      disc_number: slot.disc_mapping!.disc_number,
      output_bytes: 3_900,
      md5: 'a'.repeat(32),
    }])).toEqual([expect.objectContaining({ slot_id: slot.slot_id, status: 'verified' })])

    expect(() => convergeVolumeSlotsWithManifest([slot], [{
      slot_id: slot.slot_id,
      ordinal: slot.ordinal,
      disc_number: 'TEST20260730-WRONG',
      output_bytes: 3_900,
      md5: 'a'.repeat(32),
    }])).toThrow('MANIFEST_SLOT_MISMATCH')
  })

  it('rejects duplicate lineage or ordinal values during replan', () => {
    expect(() => reconcileVolumeSlots([], [
      { ordinal: 1, lineage_key: 'lineage-SYNTHETIC-A', planned_input_bytes: 1 },
      { ordinal: 1, lineage_key: 'lineage-SYNTHETIC-A', planned_input_bytes: 2 },
    ], 2, lineage => lineage)).toThrow('INVALID_ARCHIVE_PLAN')
  })
})
