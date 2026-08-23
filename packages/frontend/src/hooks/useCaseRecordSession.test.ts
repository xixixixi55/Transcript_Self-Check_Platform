import { describe, expect, it } from 'vitest'
import type { InspectionReport, OpaqueAssetRef } from '@biji/shared/types'
import { applyReportEdit } from '@biji/shared/utils'
import { shouldHydrateServerDraft } from './useCaseDraftHydration'
import { reportWithPhotoAssetRefs } from './useCaseRecordSession'

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

  it('does not hydrate an older server snapshot after a local save advances the revision', () => {
    expect(shouldHydrateServerDraft('case-synthetic-1', draft('case-synthetic-1', 4), 'case-synthetic-1:6', 0)).toBe(false)
  })

  it('hydrates a newer server revision after local changes settle', () => {
    expect(shouldHydrateServerDraft('case-synthetic-1', draft('case-synthetic-1', 7), 'case-synthetic-1:6', 0)).toBe(true)
  })

  it('projects dragged inspector order to the current report only', () => {
    const report = {
      introduction: {
        inspectors: [
          { name: 'SYNTHETIC-A', unit: 'SYNTHETIC-UNIT-A', badge_number: 'SYNTHETIC-001' },
          { name: 'SYNTHETIC-B', unit: 'SYNTHETIC-UNIT-B', badge_number: 'SYNTHETIC-002' },
        ],
      },
    } as InspectionReport
    const dragged = [
      { name: 'SYNTHETIC-B', unit: 'SYNTHETIC-UNIT-B', police_number: 'SYNTHETIC-002', selected_order: 0 },
      { name: 'SYNTHETIC-A', unit: 'SYNTHETIC-UNIT-A', police_number: 'SYNTHETIC-001', selected_order: 1 },
    ]

    const edited = applyReportEdit(report, 'introduction.inspector_snapshots', dragged)

    expect(edited.introduction.inspectors.map(item => item.name)).toEqual(['SYNTHETIC-B', 'SYNTHETIC-A'])
  })

  it('persists photo ids and deterministic material groups from asset reference order', () => {
    const report = {
      introduction: {
        evidence_list: [{ id: 'SYNTHETIC-MATERIAL', evidence_number: 'SYNTHETIC-1' }],
      },
      attachments: { extract_list: { columns: [], rows: [] }, photo_ids: [], disc_number: '' },
    } as unknown as InspectionReport
    const refs = ['asset-synthetic-front', 'asset-synthetic-back'].map(assetId => ({
      asset_id: assetId, asset_kind: 'image', fingerprint: `fingerprint-${assetId}`,
      metadata: { file_name: `${assetId}.png`, extension: '.png' },
    })) as OpaqueAssetRef[]

    const updated = reportWithPhotoAssetRefs(report, refs)

    expect(updated.attachments.photo_ids).toEqual(refs.map(ref => ref.asset_id))
    expect(updated.attachments.photo_groups).toEqual([{
      material_id: 'SYNTHETIC-MATERIAL', material_number: 'SYNTHETIC-1',
      display_text: '检材SYNTHETIC-1照片',
      ordered_image_ids: refs.map(ref => ref.asset_id), source_order: 1,
    }])
  })
})
