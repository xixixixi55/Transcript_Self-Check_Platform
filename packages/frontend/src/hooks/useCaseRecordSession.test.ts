import { describe, expect, it } from 'vitest'
import type { InspectionReport } from '@biji/shared/types'
import { shouldHydrateServerDraft } from './useCaseDraftHydration'
import { sharedPatchForEdit } from './useCaseRecordSession'

describe('shouldHydrateServerDraft', () => {
  const draft = (caseId: string, revision: number) => ({ case_id: caseId, revision })

  it('does not rehydrate the editor for a pending refresh at the same draft revision', () => {
    expect(shouldHydrateServerDraft('case-synthetic-1', draft('case-synthetic-1', 4), 'case-synthetic-1:4', 0)).toBe(false)
  })

  it('does not overwrite local edits when the server revision changes during editing', () => {
    expect(shouldHydrateServerDraft('case-synthetic-1', draft('case-synthetic-1', 5), 'case-synthetic-1:4', 1)).toBe(false)
  })

  it('hydrates a different case even when its revision matches the previous case', () => {
    expect(shouldHydrateServerDraft('case-synthetic-2', draft('case-synthetic-2', 4), 'case-synthetic-1:4', 0)).toBe(true)
  })

  it('keeps inspector order and extracts only the disc-number prefix', () => {
    const report = {
      introduction: {
        inspectors: [
          { name: 'SYNTHETIC-A', unit: 'SYNTHETIC-UNIT-A', badge_number: 'SYNTHETIC-001' },
          { name: 'SYNTHETIC-B', unit: 'SYNTHETIC-UNIT-B', badge_number: 'SYNTHETIC-002' },
        ],
      },
      attachments: { disc_number: 'ABC20260729-01' },
    } as InspectionReport

    expect(sharedPatchForEdit(report, 'introduction.inspectors')).toEqual({
      inspector_order: [
        'SYNTHETIC-A|SYNTHETIC-UNIT-A|SYNTHETIC-001',
        'SYNTHETIC-B|SYNTHETIC-UNIT-B|SYNTHETIC-002',
      ],
    })
    expect(sharedPatchForEdit(report, 'attachments.disc_number')).toEqual({
      disc_number_prefix: 'ABC',
    })
  })
})
