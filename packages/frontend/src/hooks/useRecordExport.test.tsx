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
    entrust_unit: '单位', entrust_persons: ['人员'], entrust_time: '', case_summary: '摘要', evidence_list: [],
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
})

function screenButton(): HTMLButtonElement {
  return document.querySelector('button') as HTMLButtonElement
}
