import type { InspectionReport } from '../types'
import { buildMaterialPhotoGroups } from './materialPhotoGroups'

declare const describe: (name: string, run: () => void) => void
declare const it: (name: string, run: () => void) => void
declare const expect: any

describe('buildMaterialPhotoGroups', () => {
  it('pairs ordered image ids with materials in source order', () => {
    const report = {
      introduction: {
        evidence_list: [
          { id: 'SYNTHETIC-MATERIAL-1', evidence_number: 'SYNTHETIC-1' },
          { id: 'SYNTHETIC-MATERIAL-2', evidence_number: 'SYNTHETIC-2' },
        ],
      },
    } as InspectionReport

    expect(buildMaterialPhotoGroups(report, [
      'asset-synthetic-1-front', 'asset-synthetic-1-back',
      'asset-synthetic-2-front', 'asset-synthetic-2-back',
    ])).toEqual([
      {
        material_id: 'SYNTHETIC-MATERIAL-1', material_number: 'SYNTHETIC-1',
        display_text: '检材SYNTHETIC-1照片',
        ordered_image_ids: ['asset-synthetic-1-front', 'asset-synthetic-1-back'],
        source_order: 1,
      },
      {
        material_id: 'SYNTHETIC-MATERIAL-2', material_number: 'SYNTHETIC-2',
        display_text: '检材SYNTHETIC-2照片',
        ordered_image_ids: ['asset-synthetic-2-front', 'asset-synthetic-2-back'],
        source_order: 2,
      },
    ])
  })
})
