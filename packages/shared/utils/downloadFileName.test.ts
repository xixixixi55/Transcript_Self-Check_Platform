import {
  getDefaultWordDownloadName,
  normalizeWordDownloadName,
  toWordDownloadName,
  validateWordDownloadName,
} from './downloadFileName'

declare const describe: (name: string, run: () => void) => void
declare const it: (name: string, run: () => void) => void
declare const expect: any

describe('T007T Word download names', () => {
  it('uses the document number only when it exists and adds exactly one extension', () => {
    expect(getDefaultWordDownloadName('SYNTHETIC-DOC')).toBe('SYNTHETIC-DOC.docx')
    expect(getDefaultWordDownloadName('')).toBe('')
    expect(normalizeWordDownloadName(' SYNTHETIC-name.docx.docx ')).toBe('SYNTHETIC-name.docx')
  })

  it('rejects empty and Windows-invalid names before creating a DTO', () => {
    expect(validateWordDownloadName('')).toBe('自定义文件名不能为空。')
    expect(validateWordDownloadName('SYNTHETIC/result')).toContain('Windows 非法字符')
    expect(toWordDownloadName('SYNTHETIC/result')).toBeNull()
    expect(toWordDownloadName('SYNTHETIC-result')).toEqual({ download_name: 'SYNTHETIC-result.docx' })
  })
})
