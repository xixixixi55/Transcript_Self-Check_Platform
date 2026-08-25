import { Button, Input } from 'antd'
import type { InspectionReport } from '@biji/shared/types'
import type { GuidedReviewAction } from '../hooks/useGuidedReviewCards'
import { REVIEW_TARGET_IDS } from '../hooks/useReviewChecklist'
import { DateTimeField } from './DateTimeField'
import { DocumentNumberEditor } from './DocumentNumberEditor'
import { normalizeEntrustPersons } from './ReviewIntroductionSection'

interface Props {
  action: GuidedReviewAction
  report: InspectionReport
  updateReport: (path: string, value: unknown) => void
  readOnly: boolean
  specialContent?: React.ReactNode
  onEvidenceCompletenessChange?: (confirmed: boolean) => void
  onOpenFullEditor?: (targetId?: string) => void
}

interface TextField {
  path: string
  value: string
  multiline?: boolean
  transform?: (value: string) => unknown
}

function resultField(report: InspectionReport, targetId: string): TextField | null {
  const keys = ['evidence_number', 'data_summary', 'rar_filename', 'md5_hash', 'file_size'] as const
  const key = keys.find(candidate => targetId === REVIEW_TARGET_IDS.result(candidate))
  return key ? {
    path: `inspection.result.${key}`,
    value: report.inspection.result[key],
    multiline: key === 'data_summary',
  } : null
}

function textField(report: InspectionReport, targetId: string): TextField | null {
  const introduction = report.introduction
  const inspection = report.inspection
  const primarySoftware = inspection.primary_software
  const fields: Record<string, TextField> = {
    [REVIEW_TARGET_IDS.documentNumber]: { path: 'document_number', value: report.document_number },
    [REVIEW_TARGET_IDS.entrustUnit]: { path: 'introduction.entrust_unit', value: introduction.entrust_unit },
    [REVIEW_TARGET_IDS.entrustPersons]: {
      path: 'introduction.entrust_persons', value: introduction.entrust_persons.join('、'),
      transform: normalizeEntrustPersons,
    },
    [REVIEW_TARGET_IDS.caseSummary]: { path: 'introduction.case_summary', value: introduction.case_summary, multiline: true },
    [REVIEW_TARGET_IDS.inspectionRequirement]: {
      path: 'introduction.inspection_requirement', value: introduction.inspection_requirement, multiline: true,
    },
    [REVIEW_TARGET_IDS.inspectionPlace]: { path: 'introduction.inspection_place', value: introduction.inspection_place },
    [REVIEW_TARGET_IDS.inspectionMethod]: { path: 'inspection.method', value: inspection.method, multiline: true },
    [REVIEW_TARGET_IDS.hardwareDevice]: { path: 'inspection.hardware_device', value: inspection.hardware_device },
    [REVIEW_TARGET_IDS.primarySoftwareName]: {
      path: 'inspection.primary_software.name', value: primarySoftware?.name || '',
    },
    [REVIEW_TARGET_IDS.primarySoftwareVersion]: {
      path: 'inspection.primary_software.version', value: primarySoftware?.version || '',
    },
    [REVIEW_TARGET_IDS.discNumber]: { path: 'attachments.disc_number', value: report.attachments.disc_number },
  }
  return fields[targetId] || resultField(report, targetId)
}

export function GuidedReviewCard({
  action, report, updateReport, readOnly, specialContent,
  onEvidenceCompletenessChange, onOpenFullEditor,
}: Props) {
  if (specialContent) return <div className="guided-review-card__control">{specialContent}</div>
  const pending = action.pendingItem
  if (!pending) return <p className="guided-review-card__status">{action.description}</p>
  const { targetId, fieldLabel } = pending

  if (targetId === REVIEW_TARGET_IDS.documentNumber && report.document_number_template) return (
    <fieldset disabled={readOnly} className="guided-review-card__fieldset">
      <DocumentNumberEditor template={report.document_number_template}
        documentNumber={report.document_number} onChange={value => updateReport('document_number', value)} />
    </fieldset>
  )
  if (targetId === REVIEW_TARGET_IDS.entrustTime) return (
    <fieldset disabled={readOnly} className="guided-review-card__fieldset">
      <DateTimeField label={fieldLabel} precision="date" value={report.introduction.entrust_time}
        onChange={value => updateReport('introduction.entrust_time', value)} />
    </fieldset>
  )
  if (targetId === REVIEW_TARGET_IDS.inspectionTimeRange) return (
    <fieldset disabled={readOnly} className="guided-review-card__fieldset">
      <DateTimeField label={fieldLabel} precision="minute-range" value={report.introduction.inspection_time_range}
        onChange={value => updateReport('introduction.inspection_time_range', value)} />
    </fieldset>
  )
  if (targetId === REVIEW_TARGET_IDS.burningDate) return (
    <fieldset disabled={readOnly} className="guided-review-card__fieldset">
      <DateTimeField label={fieldLabel} precision="date" value={report.attachments.burning_date || ''}
        onChange={value => updateReport('attachments.burning_date', value)} />
    </fieldset>
  )
  if (targetId === REVIEW_TARGET_IDS.evidenceCompleteness) return (
    <Button type="primary" disabled={readOnly}
      onClick={() => onEvidenceCompletenessChange?.(true)}>确认检材信息完整</Button>
  )

  const field = textField(report, targetId)
  if (field) {
    const change = (value: string) => updateReport(field.path, field.transform ? field.transform(value) : value)
    return (
      <label className="guided-review-card__field">
        <span>{fieldLabel}</span>
        {field.multiline
          ? <Input.TextArea aria-label={fieldLabel} value={field.value} disabled={readOnly}
              autoSize={{ minRows: 2, maxRows: 5 }} onChange={event => change(event.target.value)} />
          : <Input aria-label={fieldLabel} value={field.value} disabled={readOnly}
              onChange={event => change(event.target.value)} />}
      </label>
    )
  }

  return (
    <div className="guided-review-card__fallback">
      <p>此事项使用完整审核编辑中的现有结构化控件办理。</p>
      <Button onClick={() => onOpenFullEditor?.(targetId)}>在完整审核编辑中处理此项</Button>
    </div>
  )
}
