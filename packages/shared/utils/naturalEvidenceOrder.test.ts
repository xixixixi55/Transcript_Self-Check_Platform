import { naturalEvidenceOrder } from './naturalEvidenceOrder'

declare const describe: (name: string, run: () => void) => void
declare const it: (name: string, run: () => void) => void
declare const expect: any

describe('T007T natural evidence order', () => {
  it('uses natural number order for unique recognizable SYNTHETIC evidence numbers', () => {
    const source = [
      { evidence_id: 'SYNTHETIC-evidence-10', evidence_number: '检材10' },
      { evidence_id: 'SYNTHETIC-evidence-2', evidence_number: '检材2' },
    ]

    expect(naturalEvidenceOrder(source).map(item => item.evidence_id)).toEqual([
      'SYNTHETIC-evidence-2', 'SYNTHETIC-evidence-10',
    ])
    expect(source.map(item => item.evidence_id)).toEqual([
      'SYNTHETIC-evidence-10', 'SYNTHETIC-evidence-2',
    ])
  })

  it('keeps parser order when values are duplicated or not recognizable', () => {
    const duplicate = [
      { evidence_number: '检材02' }, { evidence_number: '检材2' },
    ]
    const unrecognized = [
      { evidence_number: 'SYNTHETIC-UNKNOWN' }, { evidence_number: '检材10' },
    ]

    expect(naturalEvidenceOrder(duplicate)).toEqual(duplicate)
    expect(naturalEvidenceOrder(unrecognized)).toEqual(unrecognized)
  })
})
