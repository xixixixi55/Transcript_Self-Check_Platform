import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ArchiveTaskResult, InspectionReport } from '@biji/shared/types'
import RecordEditorForm from './RecordEditorForm'

vi.mock('antd', () => ({
  Alert: ({ message, description }: { message?: React.ReactNode; description?: React.ReactNode }) => (
    <div>{message || '注意修改文号！'}{description}</div>
  ),
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
vi.mock('./ArchiveStatusCard', () => ({ ArchiveStatusCard: ({ showPartDownload }: { showPartDownload?: boolean }) => (
  <div data-testid="archive-status-card">{String(showPartDownload)}</div>
) }))

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
      archiveResult={{ result: {
        task_id: 'archive-task-1', case_id: 'case-synthetic', manifest_id: 'manifest-synthetic',
        plan_row_revision: 1, verified_slots: [], assets: [], parts: [], finished_at: '2026-08-13T00:00:00Z',
      } satisfies ArchiveTaskResult, loading: false, error: null }}
      workbenchMode />)

    expect(screen.getByText('审核编辑')).toBeTruthy()
    expect(screen.queryByText('请核对解析内容；修改会按 revision 自动保存到案件草稿。')).toBeNull()
    expect(screen.getByTestId('evidence-editor')).toBeTruthy()
    expect(screen.getByTestId('image-uploader')).toBeTruthy()
    expect(screen.queryByText('附件3：光盘编号')).toBeNull()
    expect(screen.queryByLabelText('导出文件名')).toBeNull()
    expect(screen.getByTestId('archive-status-card').textContent).toBe('false')
  })

  it('keeps the read-only attachment date summary for a saved valid disc number', () => {
    const reportWithDisc = JSON.parse(JSON.stringify(report)) as InspectionReport
    reportWithDisc.attachments.disc_number = 'GP20260718-001'
    render(<RecordEditorForm report={reportWithDisc} updateReport={vi.fn()} onExport={vi.fn()} exporting={false}
      onBackToUpload={vi.fn()} deviceOptions={[]} photoFiles={[]} onPhotoFilesChange={vi.fn()}
      workbenchMode />)

    expect(screen.queryByText('附件3：光盘编号')).toBeNull()
    expect(screen.getByText('附件摘要/附件3日期')).toBeTruthy()
    expect(screen.getByText('后续光盘编号将在最终卷数确定后按序号自动生成。')).toBeTruthy()
  })

  it('keeps the read-only validation feedback for a saved invalid disc number', () => {
    const reportWithDisc = JSON.parse(JSON.stringify(report)) as InspectionReport
    reportWithDisc.attachments.disc_number = 'INVALID-DISC'
    render(<RecordEditorForm report={reportWithDisc} updateReport={vi.fn()} onExport={vi.fn()} exporting={false}
      onBackToUpload={vi.fn()} deviceOptions={[]} photoFiles={[]} onPhotoFilesChange={vi.fn()}
      workbenchMode />)

    expect(screen.queryByText('附件3：光盘编号')).toBeNull()
    expect(screen.getByText('首个光盘编号格式或日期无效，导出前必须修正。')).toBeTruthy()
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

  it('在案件简要标题旁提醒人工核对，并在尾部存在空白时保留清理提示', () => {
    const reportWithWhitespace = JSON.parse(JSON.stringify(report)) as InspectionReport
    reportWithWhitespace.introduction.case_summary = '合成案件摘要  \n'
    render(<RecordEditorForm report={reportWithWhitespace} updateReport={vi.fn()} onExport={vi.fn()}
      exporting={false} onBackToUpload={vi.fn()} deviceOptions={[]} photoFiles={[]}
      onPhotoFilesChange={vi.fn()} />)

    expect(screen.getByText('（请注意人工核对）')).toBeTruthy()
    expect(screen.queryByText(/案件简要情况由报告自动解析/)).toBeNull()
    expect(screen.getByText('当前内容末尾存在多余回车、空格或制表符，请检查并删除。')).toBeTruthy()
  })

  it('案件简要没有尾部空白时仅显示标题旁人工核对提示', () => {
    render(<RecordEditorForm report={report} updateReport={vi.fn()} onExport={vi.fn()}
      exporting={false} onBackToUpload={vi.fn()} deviceOptions={[]} photoFiles={[]}
      onPhotoFilesChange={vi.fn()} />)

    expect(screen.getByText('（请注意人工核对）')).toBeTruthy()
    expect(screen.queryByText('当前内容末尾存在多余回车、空格或制表符，请检查并删除。')).toBeNull()
  })

  it('委托单位前缀与委托单位使用响应式双列容器且标题精简', () => {
    const view = render(<RecordEditorForm report={report} updateReport={vi.fn()} onExport={vi.fn()}
      exporting={false} onBackToUpload={vi.fn()} deviceOptions={[]} photoFiles={[]}
      onPhotoFilesChange={vi.fn()} />)

    const row = view.container.querySelector('.review-field-row--entrust-unit')
    expect(row).toBeTruthy()
    expect(row?.textContent).toContain('委托单位前缀')
    expect(row?.textContent).toContain('（一）委托单位')
    expect(screen.queryByText('委托单位前缀（共享默认值）')).toBeNull()
  })

  it('单独编辑可为空的委托单位共享前缀，不改写报告识别单位', () => {
    const updateReport = vi.fn()
    const reportWithPrefix = JSON.parse(JSON.stringify(report)) as InspectionReport
    reportWithPrefix.introduction.entrust_unit_prefix = 'SYNTHETIC-公安分局'
    reportWithPrefix.introduction.entrust_unit = 'SYNTHETIC-派出所'

    render(<RecordEditorForm report={reportWithPrefix} updateReport={updateReport} onExport={vi.fn()}
      exporting={false} onBackToUpload={vi.fn()} deviceOptions={[]} photoFiles={[]}
      onPhotoFilesChange={vi.fn()} />)

    expect(screen.getByDisplayValue('SYNTHETIC-派出所')).toBeTruthy()
    const prefix = screen.getByDisplayValue('SYNTHETIC-公安分局')
    fireEvent.change(prefix, { target: { value: '' } })
    expect(updateReport).toHaveBeenCalledWith('introduction.entrust_unit_prefix', '')
  })

  it('将委托人的常见分隔符统一显示为顿号并按数组保存', () => {
    const updateReport = vi.fn()
    const reportWithPersons = JSON.parse(JSON.stringify(report)) as InspectionReport
    reportWithPersons.introduction.entrust_persons = ['SYNTHETIC-A; SYNTHETIC-B', 'SYNTHETIC-C']

    render(<RecordEditorForm report={reportWithPersons} updateReport={updateReport} onExport={vi.fn()}
      exporting={false} onBackToUpload={vi.fn()} deviceOptions={[]} photoFiles={[]}
      onPhotoFilesChange={vi.fn()} />)

    const field = screen.getByDisplayValue('SYNTHETIC-A、SYNTHETIC-B、SYNTHETIC-C')
    fireEvent.change(field, { target: { value: 'SYNTHETIC-D； SYNTHETIC-E/SYNTHETIC-F' } })
    expect(updateReport).toHaveBeenCalledWith('introduction.entrust_persons', [
      'SYNTHETIC-D', 'SYNTHETIC-E', 'SYNTHETIC-F',
    ])
  })

  it('审核结果中的 MD5 以大写显示并以大写提交', () => {
    const updateReport = vi.fn()
    const reportWithMd5 = JSON.parse(JSON.stringify(report)) as InspectionReport
    reportWithMd5.inspection.result.md5_hash = 'a1b2c3d4'
    render(<RecordEditorForm report={reportWithMd5} updateReport={updateReport} onExport={vi.fn()}
      exporting={false} onBackToUpload={vi.fn()} deviceOptions={[]} photoFiles={[]}
      onPhotoFilesChange={vi.fn()} />)

    const field = screen.getByDisplayValue('A1B2C3D4')
    fireEvent.change(field, { target: { value: 'deadbeef' } })
    expect(updateReport).toHaveBeenCalledWith('inspection.result.md5_hash', 'DEADBEEF')
  })
})
