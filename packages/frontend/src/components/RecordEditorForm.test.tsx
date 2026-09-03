import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { ArchiveTaskResult, InspectionReport } from '@biji/shared/types'
import RecordEditorForm from './RecordEditorForm'

vi.mock('antd', () => ({
  Alert: ({ message, description }: { message?: React.ReactNode; description?: React.ReactNode }) => (
    <div>{message || '注意修改文号！'}{description}</div>
  ),
  Button: ({ children, icon, onClick, disabled, loading, shape: _shape, size: _size, danger: _danger, ...props }: any) => (
    <button {...props} onClick={onClick} disabled={disabled || loading}>{icon}{children}</button>
  ),
  Divider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Input: ({ value, onChange, ...props }: { value?: string; onChange?: (event: { target: { value: string } }) => void }) => (
    <input {...props} value={value || ''} onChange={event => onChange?.({ target: { value: event.target.value } })} />
  ),
  Space: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
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
  FileWordOutlined: () => null,
  HomeOutlined: () => null,
  InfoCircleOutlined: () => null,
  LoadingOutlined: () => null,
  RollbackOutlined: () => null,
  SaveOutlined: () => null,
  WarningOutlined: () => null,
}))
vi.mock('./EditableField', () => ({ default: (props: { value?: string; onChange?: (value: string) => void }) => (
  <input data-testid="editable-field" value={props.value || ''}
    onChange={event => props.onChange?.(event.target.value)} />
) }))
vi.mock('./EvidenceEditor', () => ({ default: ({ onChange }: { onChange: (items: unknown[]) => void }) => (
  <div data-testid="evidence-editor">
    <button type="button" onClick={() => onChange([])}>修改合成检材</button>
  </div>
) }))
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
  it('只填写文号编号并组合完整文号，同时保留前导零', () => {
    const updateReport = vi.fn()
    const templatedReport = {
      ...report,
      document_number: 'SYN-TEST〔2026〕00142号',
      document_number_template: { prefix: 'SYN-TEST〔2026〕', suffix: '号' },
    }

    render(<RecordEditorForm report={templatedReport} updateReport={updateReport}
      onExport={vi.fn()} exporting={false} onBackToUpload={vi.fn()}
      deviceOptions={[]} photoFiles={[]} onPhotoFilesChange={vi.fn()} />)

    const sequence = screen.getByRole('textbox', { name: '文号编号' })
    expect((sequence as HTMLInputElement).value).toBe('00142')
    fireEvent.change(sequence, { target: { value: '00143' } })
    expect(updateReport).toHaveBeenCalledWith('document_number', 'SYN-TEST〔2026〕00143号')
  })

  it('没有格式快照或文号不匹配时继续编辑完整文号', () => {
    const updateReport = vi.fn()
    const unmatchedReport = {
      ...report,
      document_number_template: { prefix: 'OTHER〔2026〕', suffix: '号' },
    }
    render(<RecordEditorForm report={unmatchedReport} updateReport={updateReport} onExport={vi.fn()}
      exporting={false} onBackToUpload={vi.fn()} deviceOptions={[]} photoFiles={[]}
      onPhotoFilesChange={vi.fn()} />)

    expect(screen.queryByRole('textbox', { name: '文号编号' })).toBeNull()
    expect(screen.getByDisplayValue('SYN-TEST〔2026〕000001号')).toBeTruthy()
  })

  it('文号编号为空时清空完整文号，非数字输入保持在当前输入框并提示', () => {
    const updateReport = vi.fn()
    const templatedReport = {
      ...report,
      document_number: 'SYN-TEST〔2026〕142号',
      document_number_template: { prefix: 'SYN-TEST〔2026〕', suffix: '号' },
    }
    render(<RecordEditorForm report={templatedReport} updateReport={updateReport}
      onExport={vi.fn()} exporting={false} onBackToUpload={vi.fn()}
      deviceOptions={[]} photoFiles={[]} onPhotoFilesChange={vi.fn()} />)

    const sequence = screen.getByRole('textbox', { name: '文号编号' })
    fireEvent.change(sequence, { target: { value: '' } })
    expect(updateReport).toHaveBeenCalledWith('document_number', '')
    fireEvent.change(sequence, { target: { value: '14A' } })
    expect(screen.getByRole('alert').textContent).toBe('编号只能填写数字。')
    expect(updateReport).not.toHaveBeenCalledWith('document_number', 'SYN-TEST〔2026〕14A号')
  })

  it('要求人工确认检材完整性，并在确认或修改检材时更新状态', () => {
    const onEvidenceCompletenessChange = vi.fn()
    const updateReport = vi.fn()
    const view = render(<RecordEditorForm report={report} updateReport={updateReport} onExport={vi.fn()}
      exporting={false} onBackToUpload={vi.fn()} deviceOptions={[]} photoFiles={[]}
      onPhotoFilesChange={vi.fn()} onEvidenceCompletenessChange={onEvidenceCompletenessChange} />)

    fireEvent.click(screen.getByRole('button', { name: '请确认检材是否完整？' }))
    expect(onEvidenceCompletenessChange).toHaveBeenCalledWith(true)
    fireEvent.click(screen.getByRole('button', { name: '修改合成检材' }))
    expect(updateReport).toHaveBeenCalledWith('introduction.evidence_list', [])
    expect(onEvidenceCompletenessChange).toHaveBeenLastCalledWith(false)

    view.rerender(<RecordEditorForm report={report} updateReport={updateReport} onExport={vi.fn()}
      exporting={false} onBackToUpload={vi.fn()} deviceOptions={[]} photoFiles={[]}
      onPhotoFilesChange={vi.fn()} onEvidenceCompletenessChange={onEvidenceCompletenessChange}
      fieldStates={{ 'introduction.evidence_list.completeness': {
        field_path: 'introduction.evidence_list.completeness', source: 'user', confirmation: 'confirmed',
        revision: 1, last_changed_at: '2026-08-21T00:00:00.000Z',
      } }} />)
    expect(screen.queryByRole('button', { name: '请确认检材是否完整？' })).toBeNull()
  })

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
        archive_mode: 'standard_split', archive_medium: 'optical_disc',
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

  it('keeps a neutral attachment hint while the saved medium is not known', () => {
    const reportWithDisc = JSON.parse(JSON.stringify(report)) as InspectionReport
    reportWithDisc.attachments.disc_number = 'GP20260718-001'
    render(<RecordEditorForm report={reportWithDisc} updateReport={vi.fn()} onExport={vi.fn()} exporting={false}
      onBackToUpload={vi.fn()} deviceOptions={[]} photoFiles={[]} onPhotoFilesChange={vi.fn()}
      workbenchMode />)

    expect(screen.queryByText('附件3：光盘编号')).toBeNull()
    expect(screen.getByText('附件摘要/附件3日期')).toBeTruthy()
    expect(screen.getByText('压缩完成后，系统将按最终介质类型确认该编号。')).toBeTruthy()
  })

  it('keeps the read-only validation feedback for a saved invalid disc number', () => {
    const reportWithDisc = JSON.parse(JSON.stringify(report)) as InspectionReport
    reportWithDisc.attachments.disc_number = 'INVALID-DISC'
    render(<RecordEditorForm report={reportWithDisc} updateReport={vi.fn()} onExport={vi.fn()} exporting={false}
      onBackToUpload={vi.fn()} deviceOptions={[]} photoFiles={[]} onPhotoFilesChange={vi.fn()}
      workbenchMode />)

    expect(screen.queryByText('附件3：光盘编号')).toBeNull()
    expect(screen.getByText('介质编号必须符合 GP/YP 的 yyyyMMdd-序号 或 yyyyMMddXX-序号 格式且日期真实有效（XX 为两位用户标识）。')).toBeTruthy()
  })

  it('shows hard-drive attachment semantics for an oversized archive result', () => {
    const reportWithDrive = JSON.parse(JSON.stringify(report)) as InspectionReport
    reportWithDrive.attachments.disc_number = 'YP20260820-01'
    render(<RecordEditorForm report={reportWithDrive} updateReport={vi.fn()} onExport={vi.fn()} exporting={false}
      onBackToUpload={vi.fn()} deviceOptions={[]} photoFiles={[]} onPhotoFilesChange={vi.fn()}
      archiveResult={{ result: {
        task_id: 'archive-task-hard-drive', case_id: 'case-synthetic', manifest_id: 'manifest-hard-drive',
        archive_mode: 'oversized_single_volume', archive_medium: 'hard_drive',
        plan_row_revision: 1, verified_slots: [], assets: [], parts: [], finished_at: '2026-08-20T00:00:00Z',
      } satisfies ArchiveTaskResult, loading: false, error: null }}
      workbenchMode />)

    expect(screen.getByText('该硬盘编号对应唯一完整 RAR。')).toBeTruthy()
    expect(screen.queryByText('后续光盘编号将在最终卷数确定后按序号自动生成。')).toBeNull()
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
    expect(screen.getByTestId('image-uploader').closest('#review-target-material-photos')).toBeTruthy()
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

  it('不展示委托单位前缀并保留委托单位编辑', () => {
    const updateReport = vi.fn()
    const reportWithPrefix = JSON.parse(JSON.stringify(report)) as InspectionReport
    ;(reportWithPrefix.introduction as unknown as Record<string, unknown>).entrust_unit_prefix = 'SYNTHETIC-公安分局'
    reportWithPrefix.introduction.entrust_unit = 'SYNTHETIC-派出所'

    render(<RecordEditorForm report={reportWithPrefix} updateReport={updateReport} onExport={vi.fn()}
      exporting={false} onBackToUpload={vi.fn()} deviceOptions={[]} photoFiles={[]}
      onPhotoFilesChange={vi.fn()} />)

    expect(screen.getByDisplayValue('SYNTHETIC-派出所')).toBeTruthy()
    expect(screen.queryByText('委托单位前缀')).toBeNull()
    expect(screen.queryByDisplayValue('SYNTHETIC-公安分局')).toBeNull()
    fireEvent.change(screen.getByDisplayValue('SYNTHETIC-派出所'), {
      target: { value: 'SYNTHETIC-新委托单位' },
    })
    expect(updateReport).toHaveBeenCalledWith('introduction.entrust_unit', 'SYNTHETIC-新委托单位')
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
