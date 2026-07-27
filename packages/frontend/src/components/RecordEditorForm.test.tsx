import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { InspectionReport } from '@biji/shared/types'
import RecordEditorForm from './RecordEditorForm'

vi.mock('antd', () => ({
  Alert: () => <div>注意修改文号！</div>,
  Button: ({ children, onClick, disabled }: { children: React.ReactNode; onClick?: () => void; disabled?: boolean }) => <button onClick={onClick} disabled={disabled}>{children}</button>,
  Checkbox: ({ checked, onChange, children }: { checked?: boolean; onChange?: (event: { target: { checked: boolean } }) => void; children: React.ReactNode }) => (
    <label><input type="checkbox" checked={checked} onChange={event => onChange?.({ target: { checked: event.target.checked } })} />{children}</label>
  ),
  Divider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Input: ({ value, onChange, disabled, ...props }: { value?: string; onChange?: (event: { target: { value: string } }) => void; disabled?: boolean }) => (
    <input {...props} value={value || ''} disabled={disabled} onChange={event => onChange?.({ target: { value: event.target.value } })} />
  ),
  Space: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Typography: {
    Title: ({ children }: { children: React.ReactNode }) => <h1>{children}</h1>,
    Text: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
  },
}))

vi.mock('@ant-design/icons', () => ({
  CheckCircleOutlined: () => null,
  DownloadOutlined: () => null,
  EditOutlined: () => null,
  ExclamationCircleOutlined: () => null,
  InfoCircleOutlined: () => null,
  LoadingOutlined: () => null,
  SaveOutlined: () => null,
  WarningOutlined: () => null,
}))
vi.mock('./EditableField', () => ({ default: (props: { value?: string; onChange?: (value: string) => void }) => (
  <input data-testid="editable-field" value={props.value || ''}
    onChange={event => props.onChange?.(event.target.value)} />
) }))
vi.mock('./EvidenceEditor', () => ({ default: () => <div data-testid="evidence-editor" /> }))
vi.mock('./InspectorEditor', () => ({ default: () => <div data-testid="inspector-editor" /> }))
vi.mock('./ProcessStepsEditor', () => ({ default: () => <div data-testid="process-steps-editor" /> }))
vi.mock('./SoftwareToolsList', () => ({ default: () => <div data-testid="software-tools-list" /> }))
vi.mock('./ExtractListEditor', () => ({ default: () => <div data-testid="extract-list-editor" /> }))
vi.mock('./ImageUploader', () => ({ default: () => <div data-testid="image-uploader" /> }))
vi.mock('./ArchiveStatusCard', () => ({ ArchiveStatusCard: () => null }))

const report: InspectionReport = {
  title: '电子数据检查笔录', document_number: 'SYN-TEST〔2026〕000001号',
  introduction: {
    entrust_unit: '单位', entrust_persons: ['人员'], entrust_time: '时间', case_summary: '案情',
    evidence_list: [], inspection_requirement: '要求', inspection_time_range: '范围',
    inspectors: [], inspection_place: '地点',
  },
  inspection: {
    method: '方法', hardware_device: '设备', software_tools: [], process_steps: [],
    result: { evidence_number: '', software_name: '', software_version: '', data_summary: '', rar_filename: '', md5_hash: '', file_size: '' },
  },
  attachments: { extract_list: { columns: [], rows: [] }, photo_ids: [], disc_number: '' },
}

describe('RecordEditorForm', () => {
  it('locks the export filename until custom naming is enabled', () => {
    const onCustomFileNameChange = vi.fn()
    const onExportFileNameChange = vi.fn()
    const view = render(<RecordEditorForm report={report} updateReport={vi.fn()} onExport={vi.fn()} exporting={false}
      onBackToUpload={vi.fn()} deviceOptions={[]} photoFiles={[]} onPhotoFilesChange={vi.fn()}
      exportFileName="SYN-TEST〔2026〕000001号.docx" customFileName={false}
      onCustomFileNameChange={onCustomFileNameChange} onExportFileNameChange={onExportFileNameChange} />)

    const filenameInput = screen.getByLabelText('导出文件名') as HTMLInputElement
    expect(filenameInput.disabled).toBe(true)
    fireEvent.click(screen.getByText('自定义文件名'))
    expect(onCustomFileNameChange).toHaveBeenCalledWith(true)

    view.rerender(<RecordEditorForm report={report} updateReport={vi.fn()} onExport={vi.fn()} exporting={false}
      onBackToUpload={vi.fn()} deviceOptions={[]} photoFiles={[]} onPhotoFilesChange={vi.fn()}
      exportFileName="自定义名称" customFileName={true}
      onCustomFileNameChange={onCustomFileNameChange} onExportFileNameChange={onExportFileNameChange} />)
    expect((screen.getByLabelText('导出文件名') as HTMLInputElement).disabled).toBe(false)
    fireEvent.change(screen.getByLabelText('导出文件名'), { target: { value: '新名称' } })
    expect(onExportFileNameChange).toHaveBeenCalledWith('新名称')
  })

  it('saves and clears the six report defaults and edits the disc prefix', () => {
    const saveDefaults = vi.fn()
    const clearDefaults = vi.fn()
    const savePrefix = vi.fn()
    render(<RecordEditorForm report={report} updateReport={vi.fn()} onExport={vi.fn()} exporting={false}
      onBackToUpload={vi.fn()} deviceOptions={[]} photoFiles={[]} onPhotoFilesChange={vi.fn()}
      exportFileName="record.docx" customFileName={false} hasReportDefaults={true} defaultDiscPrefix="测试公"
      onSaveReportDefaults={saveDefaults} onClearReportDefaults={clearDefaults}
      onDefaultDiscPrefixChange={savePrefix} onCustomFileNameChange={vi.fn()} onExportFileNameChange={vi.fn()} />)

    fireEvent.click(screen.getByText('保存当前六项为默认值'))
    expect(saveDefaults).toHaveBeenCalled()
    expect(screen.getByText('保存范围：文号、检查地点、检查方法、检查硬件设备、检查人员、光盘编号前缀')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('默认光盘编号前缀'), { target: { value: '新前缀' } })
    expect(savePrefix).toHaveBeenCalledWith('新前缀')
    fireEvent.click(screen.getByText('清除全部默认值'))
    expect(clearDefaults).toHaveBeenCalled()
  })

  it('keeps the full editor controls when rendered by the case workbench', () => {
    const saveDefaults = vi.fn()
    render(<RecordEditorForm report={report} updateReport={vi.fn()} onExport={vi.fn()} exporting={false}
      onBackToUpload={vi.fn()} deviceOptions={[]} photoFiles={[]} onPhotoFilesChange={vi.fn()}
      exportFileName="record.docx" customFileName={true} workbenchMode
      onCustomFileNameChange={vi.fn()} onExportFileNameChange={vi.fn()}
      onSaveReportDefaults={saveDefaults} defaultDiscPrefix="SYN-" />)

    expect(screen.getByText('审核编辑')).toBeTruthy()
    expect(screen.getByTestId('evidence-editor')).toBeTruthy()
    expect(screen.getByTestId('image-uploader')).toBeTruthy()
    expect((screen.getByLabelText('导出文件名') as HTMLInputElement).disabled).toBe(false)
    fireEvent.click(screen.getByText('保存当前六项为默认值'))
    expect(saveDefaults).toHaveBeenCalledTimes(1)
  })

  it('集成所有审核编辑区域和附件编辑器', () => {
    render(<RecordEditorForm report={report} updateReport={vi.fn()} onExport={vi.fn()} exporting={false}
      onBackToUpload={vi.fn()} deviceOptions={[]} photoFiles={[]} onPhotoFilesChange={vi.fn()}
      exportFileName="SYN-TEST〔2026〕000001号.docx" customFileName={false}
      onCustomFileNameChange={vi.fn()} onExportFileNameChange={vi.fn()} />)

    expect(screen.getByTestId('evidence-editor')).toBeTruthy()
    expect(screen.getByTestId('inspector-editor')).toBeTruthy()
    expect(screen.getByTestId('process-steps-editor')).toBeTruthy()
    expect(screen.getByTestId('software-tools-list')).toBeTruthy()
    expect(screen.getByTestId('extract-list-editor')).toBeTruthy()
    expect(screen.getByTestId('image-uploader')).toBeTruthy()
    expect(screen.getAllByTestId('editable-field').length).toBeGreaterThan(0)
    expect(screen.getByDisplayValue('即时通讯、手机信息')).toBeTruthy()
  })

  it('keeps a non-empty user-entered data summary', () => {
    const updateReport = vi.fn()
    const reportWithSummary = JSON.parse(JSON.stringify(report)) as InspectionReport
    reportWithSummary.inspection.result.data_summary = '用户自定义摘要'
    render(<RecordEditorForm report={reportWithSummary} updateReport={updateReport} onExport={vi.fn()}
      exporting={false} onBackToUpload={vi.fn()} deviceOptions={[]} photoFiles={[]}
      onPhotoFilesChange={vi.fn()} exportFileName="检查笔录.docx" customFileName={false}
      onCustomFileNameChange={vi.fn()} onExportFileNameChange={vi.fn()} />)

    const field = screen.getByDisplayValue('用户自定义摘要')
    fireEvent.change(field, { target: { value: '   ' } })
    expect(updateReport).toHaveBeenCalledWith('inspection.result.data_summary', '即时通讯、手机信息')
  })
})
