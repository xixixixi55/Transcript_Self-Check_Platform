import { describe, expect, it } from 'vitest'
import type { InspectionReport, OpaqueAssetRef } from '@biji/shared/types'
import { applyReportEdit } from '@biji/shared/utils'
import { shouldHydrateServerDraft } from './useCaseDraftHydration'
import { reportWithPhotoAssetRefs, sharedPatchForEdit } from './useCaseRecordSession'

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

  it('creates a clearable shared patch for the entrust-unit prefix', () => {
    const report = {
      introduction: { entrust_unit_prefix: ' SYNTHETIC-公安分局 ' },
    } as InspectionReport

    expect(sharedPatchForEdit(report, 'introduction.entrust_unit_prefix')).toEqual({
      entrust_unit_prefix: 'SYNTHETIC-公安分局',
    })
    report.introduction.entrust_unit_prefix = ''
    expect(sharedPatchForEdit(report, 'introduction.entrust_unit_prefix')).toEqual({
      entrust_unit_prefix: '',
    })
  })

  it('projects dragged inspector order to both the form and shared export input', () => {
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
    expect(sharedPatchForEdit(edited, 'introduction.inspector_snapshots')).toEqual({
      inspector_order: [
        'SYNTHETIC-B|SYNTHETIC-UNIT-B|SYNTHETIC-002',
        'SYNTHETIC-A|SYNTHETIC-UNIT-A|SYNTHETIC-001',
      ],
    })
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
