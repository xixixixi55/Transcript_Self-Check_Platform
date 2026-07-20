import React from 'react'
import { fireEvent, render, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { InspectionReport } from '@biji/shared/types'
import { useRecordExport } from './useRecordExport'

const post = vi.hoisted(() => vi.fn())
vi.mock('axios', () => ({ default: { post } }))

const report: InspectionReport = {
  title: '电子数据检查笔录', document_number: 'SYN-TEST〔2026〕001号',
  introduction: {
    entrust_unit: '单位', entrust_persons: ['人员'], entrust_time: '', case_summary: '摘要', evidence_list: [
      { id: 'material-1', evidence_number: 'JC-A', device_type: 'synthetic' },
      { id: 'material-2', evidence_number: 'JC-B', device_type: 'synthetic' },
    ],
    inspection_requirement: '要求', inspection_time_range: '', inspectors: [], inspection_place: '地点',
  },
  inspection: {
    method: '方法', hardware_device: '设备', software_tools: [], process_steps: [],
    result: { evidence_number: '1', software_name: '工具', software_version: '1', data_summary: '摘要', rar_filename: 'a.rar', md5_hash: 'md5', file_size: '1MB' },
  },
  attachments: { extract_list: { columns: [], rows: [] }, photo_ids: [], disc_number: '' },
}

function ExportHarness({ onResult }: { onResult: (value: boolean) => void }) {
  const { exportDocx } = useRecordExport()
  return <button onClick={async () => onResult(await exportDocx(report, [], undefined, undefined, 'context-1'))}>导出</button>
}

function PhotoExportHarness({ onResult }: { onResult: (value: boolean) => void }) {
  const { exportDocx } = useRecordExport()
  const files = [1, 2, 3, 4].map(index => new File([`photo-${index}`], `photo-${index}.png`))
  return <button onClick={async () => onResult(await exportDocx(report, files.map(file => file.name), files, undefined, 'context-1'))}>导出</button>
}

describe('useRecordExport', () => {
  beforeEach(() => post.mockReset())

  it('保留现有下载链路并返回成功状态', async () => {
    post.mockResolvedValueOnce({ data: { data: { manifest_id: 'manifest-1' } } })
    post.mockResolvedValueOnce({ data: new Blob(['docx']) })
    const createObjectURL = vi.fn().mockReturnValue('blob:test')
    const revokeObjectURL = vi.fn()
    Object.defineProperty(window.URL, 'createObjectURL', { configurable: true, value: createObjectURL })
    Object.defineProperty(window.URL, 'revokeObjectURL', { configurable: true, value: revokeObjectURL })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    const onResult = vi.fn()
    render(<ExportHarness onResult={onResult} />)
    fireEvent.click(screenButton())
    await waitFor(() => expect(onResult).toHaveBeenCalledWith(true))
    expect(post).toHaveBeenCalledTimes(2)
    expect(createObjectURL).toHaveBeenCalled()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:test')
    expect(click).toHaveBeenCalled()
    delete (window.URL as unknown as Record<string, unknown>).createObjectURL
    delete (window.URL as unknown as Record<string, unknown>).revokeObjectURL
    click.mockRestore()
  })

  it('导出失败时保留失败提示并返回 false', async () => {
    post.mockRejectedValueOnce(new Error('network'))
    vi.spyOn(window, 'alert').mockImplementation(() => undefined)
    const onResult = vi.fn()
    render(<ExportHarness onResult={onResult} />)
    fireEvent.click(screenButton())
    await waitFor(() => expect(onResult).toHaveBeenCalledWith(false))
    expect(window.alert).toHaveBeenCalled()
    vi.restoreAllMocks()
  })

  it('uses stable blocker codes instead of backend messages', async () => {
    post.mockRejectedValueOnce({
      response: {
        data: {
          detail: {
            blockers: [{ code: 'PRIMARY_SOFTWARE_UNCONFIRMED', message: 'raw backend detail' }],
          },
        },
      },
    })
    const alert = vi.spyOn(window, 'alert').mockImplementation(() => undefined)
    const onResult = vi.fn()
    render(<ExportHarness onResult={onResult} />)
    fireEvent.click(screenButton())
    await waitFor(() => expect(onResult).toHaveBeenCalledWith(false))
    expect(alert).toHaveBeenCalledWith(expect.stringContaining('主取证软件名称和版本必须先确认。'))
    expect(alert).not.toHaveBeenCalledWith(expect.stringContaining('raw backend detail'))
    vi.restoreAllMocks()
  })

  it('shows the even-count instruction for attachment2 odd-image code', async () => {
    post.mockRejectedValueOnce({
      response: {
        data: {
          detail: {
            blockers: [{ code: 'ATTACHMENT2_IMAGE_COUNT_ODD', message: 'unsafe raw detail' }],
          },
        },
      },
    })
    const alert = vi.spyOn(window, 'alert').mockImplementation(() => undefined)
    const onResult = vi.fn()
    render(<ExportHarness onResult={onResult} />)
    fireEvent.click(screenButton())
    await waitFor(() => expect(onResult).toHaveBeenCalledWith(false))
    expect(alert).toHaveBeenCalledWith(expect.stringContaining('图片数量必须为偶数'))
    expect(alert).not.toHaveBeenCalledWith(expect.stringContaining('unsafe raw detail'))
    vi.restoreAllMocks()
  })
})

function screenButton(): HTMLButtonElement {
  return document.querySelector('button') as HTMLButtonElement
}

describe('explicit Attachment2 material mapping', () => {
  beforeEach(() => post.mockReset())

  it('sends explicit material photo groups with stable runtime image ids', async () => {
    post.mockResolvedValueOnce({ data: { data: { manifest_id: 'manifest-1' } } })
    post.mockResolvedValueOnce({ data: new Blob(['docx']) })
    Object.defineProperty(window.URL, 'createObjectURL', { configurable: true, value: vi.fn().mockReturnValue('blob:test') })
    Object.defineProperty(window.URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    const onResult = vi.fn()
    render(<PhotoExportHarness onResult={onResult} />)
    fireEvent.click(screenButton())
    await waitFor(() => expect(onResult).toHaveBeenCalledWith(true))
    const form = post.mock.calls[0][1] as FormData
    const payload = JSON.parse(await form.get('report_json') as string)
    expect(payload.attachments.photo_ids).toEqual(['photo-1', 'photo-2', 'photo-3', 'photo-4'])
    expect(payload.attachments.photo_groups).toEqual([
      {
        material_id: 'material-1', material_number: 'JC-A', display_text: '检材JC-A照片',
        ordered_image_ids: ['photo-1', 'photo-2'], source_order: 1,
      },
      {
        material_id: 'material-2', material_number: 'JC-B', display_text: '检材JC-B照片',
        ordered_image_ids: ['photo-3', 'photo-4'], source_order: 2,
      },
    ])
    vi.restoreAllMocks()
  })
})
