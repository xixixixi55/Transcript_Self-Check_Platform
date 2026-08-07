import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { InspectionReport } from '@biji/shared/types'
import RecordEditorForm from './RecordEditorForm'

vi.mock('antd', () => ({
  Alert: ({ message }: { message?: React.ReactNode }) => <div>{message || '注意修改文号！'}</div>,
  Button: ({ children, onClick, disabled }: { children: React.ReactNode; onClick?: () => void; disabled?: boolean }) => <button onClick={onClick} disabled={disabled}>{children}</button>,
  Divider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Input: ({ value, onChange, ...props }: { value?: string; onChange?: (event: { target: { value: string } }) => void }) => (
    <input {...props} value={value || ''} onChange={event => onChange?.({ target: { value: event.target.value } })} />
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
  it('fires onExport when the export button is clicked and does not render the filename input inline', () => {
    const onExport = vi.fn()
    render(<RecordEditorForm report={report} updateReport={vi.fn()} onExport={onExport} exporting={false}
      onBackToUpload={vi.fn()} deviceOptions={[]} photoFiles={[]} onPhotoFilesChange={vi.fn()} />)

    expect(screen.queryByLabelText('导出文件名')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '导出 Word' }))
    expect(onExport).toHaveBeenCalledOnce()
  })

  it('keeps the full editor controls when rendered by the case workbench', () => {
    render(<RecordEditorForm report={report} updateReport={vi.fn()} onExport={vi.fn()} exporting={false}
      onBackToUpload={vi.fn()} deviceOptions={[]} photoFiles={[]} onPhotoFilesChange={vi.fn()}
      workbenchMode defaultDiscPrefix="SYN-" />)

    expect(screen.getByText('审核编辑')).toBeTruthy()
    expect(screen.getByTestId('evidence-editor')).toBeTruthy()
    expect(screen.getByTestId('image-uploader')).toBeTruthy()
    expect(screen.queryByLabelText('导出文件名')).toBeNull()
  })

  it('集成所有审核编辑区域和附件编辑器', () => {
    render(<RecordEditorForm report={report} updateReport={vi.fn()} onExport={vi.fn()} exporting={false}
      onBackToUpload={vi.fn()} deviceOptions={[]} photoFiles={[]} onPhotoFilesChange={vi.fn()}
      />)

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
      onPhotoFilesChange={vi.fn()} />)

    const field = screen.getByDisplayValue('用户自定义摘要')
    fireEvent.change(field, { target: { value: '   ' } })
    expect(updateReport).toHaveBeenCalledWith('inspection.result.data_summary', '即时通讯、手机信息')
  })
})
