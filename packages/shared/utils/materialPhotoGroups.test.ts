import type { InspectionReport } from '../types'
import {
  buildMaterialPhotoGroups,
  hasNumericFileName,
  parseMaterialPhotoPosition,
  sortFilesByNumericName,
} from './materialPhotoGroups'

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

describe('sortFilesByNumericName', () => {
  it('naturally sorts discontinuous and variable-width numeric file names', () => {
    const files = [
      { name: 'pic1005.png' },
      { name: 'pic10.jpg' },
      { name: 'pic1003.jpeg' },
      { name: 'pic2.png' },
    ]

    expect(sortFilesByNumericName(files).map(file => file.name)).toEqual([
      'pic2.png', 'pic10.jpg', 'pic1003.jpeg', 'pic1005.png',
    ])
  })

  it('keeps the source order when names compare equally', () => {
    const first = { name: 'pic1.png', marker: 'first' }
    const second = { name: 'pic1.png', marker: 'second' }

    expect(sortFilesByNumericName([first, second]).map(file => file.marker)).toEqual([
      'first', 'second',
    ])
  })

  it('compares every numeric segment and then the extension', () => {
    const files = [
      { name: 'case10_pic1.png' }, { name: 'case2_pic10.png' },
      { name: 'case2_pic2.png' }, { name: 'case2_pic2.jpg' },
    ]
    expect(sortFilesByNumericName(files).map(file => file.name)).toEqual([
      'case2_pic2.jpg', 'case2_pic2.png', 'case2_pic10.png', 'case10_pic1.png',
    ])
  })

  it('identifies whether a file name contains a numeric sequence', () => {
    expect(hasNumericFileName('现场照片1003.png')).toBe(true)
    expect(hasNumericFileName('现场照片.png')).toBe(false)
  })

  it('parses one-based material and photo positions without using evidence numbers', () => {
    expect(parseMaterialPhotoPosition('1-1.png')).toEqual({
      materialPosition: 1, photoPosition: 1,
    })
    expect(parseMaterialPhotoPosition('003-2.JPG')).toEqual({
      materialPosition: 3, photoPosition: 2,
    })
    expect(parseMaterialPhotoPosition('pic1003.png')).toBeNull()
  })
})
