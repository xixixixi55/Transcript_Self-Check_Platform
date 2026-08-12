import React from 'react'
import type { FieldState, InspectorLibraryRecord, InspectionReport, InspectorSnapshot } from '@biji/shared/types'
import { Alert } from 'antd'
import EvidenceEditor from './EvidenceEditor'
import InspectorEditor from './InspectorEditor'
import { DateTimeField } from './DateTimeField'
import { ReviewField } from './ReviewField'
import { REVIEW_TARGET_IDS } from '../hooks/useReviewChecklist'

interface ReviewIntroductionSectionProps {
  introduction: InspectionReport['introduction']
  updateReport: (path: string, value: any) => void
  availableInspectors: InspectorLibraryRecord[]
  inspectorLoading: boolean
  inspectorError: string | null
  fieldStates?: Record<string, FieldState>
}

function toSnapshots(introduction: InspectionReport['introduction']): InspectorSnapshot[] {
  if (Array.isArray(introduction.inspector_snapshots)) return introduction.inspector_snapshots
  return (introduction.inspectors || []).map(inspector => ({
    name: inspector.name,
    unit: inspector.unit,
    police_number: inspector.badge_number,
  }))
}

export function ReviewIntroductionSection({
  introduction,
  updateReport,
  availableInspectors,
  inspectorLoading,
  inspectorError,
  fieldStates,
}: ReviewIntroductionSectionProps) {
  const hasTrailingWhitespace = /[ \t\r\n]+$/.test(introduction.case_summary || '')
  return (
    <>
      <div className="review-field-row review-field-row--entrust-unit">
        <ReviewField label="委托单位前缀" type="text" value={introduction.entrust_unit_prefix || ''}
          onChange={value => updateReport('introduction.entrust_unit_prefix', value)} />
        <ReviewField targetId={REVIEW_TARGET_IDS.entrustUnit} label="（一）委托单位" type="text" value={introduction.entrust_unit}
          onChange={value => updateReport('introduction.entrust_unit', value)} />
      </div>
      <ReviewField targetId={REVIEW_TARGET_IDS.entrustPersons} label="（二）委托人员" type="text" value={(introduction.entrust_persons || []).join('、')}
        onChange={value => updateReport('introduction.entrust_persons', value.split(/[,，、/]/).map(item => item.trim()).filter(Boolean))} />
      <DateTimeField targetId={REVIEW_TARGET_IDS.entrustTime} label="（三）委托时间" precision="date" value={introduction.entrust_time}
        onChange={value => updateReport('introduction.entrust_time', value)} />
      <ReviewField targetId={REVIEW_TARGET_IDS.caseSummary} label="（四）案件简要情况" labelNote="（请注意人工核对）" type="textarea" value={introduction.case_summary}
        onChange={value => updateReport('introduction.case_summary', value)} />
      {hasTrailingWhitespace && <Alert
        className="review-case-summary-whitespace"
        type="warning"
        showIcon
        message="当前内容末尾存在多余回车、空格或制表符，请检查并删除。"
      />}
      <div className="review-editor-block">
        <div className="review-field__label">（五）检材情况</div>
        <EvidenceEditor items={introduction.evidence_list || []}
          fieldStates={fieldStates}
          onChange={value => updateReport('introduction.evidence_list', value)} />
      </div>
      <ReviewField targetId={REVIEW_TARGET_IDS.inspectionRequirement} label="（六）检查要求" type="textarea" value={introduction.inspection_requirement}
        onChange={value => updateReport('introduction.inspection_requirement', value)} />
      <DateTimeField targetId={REVIEW_TARGET_IDS.inspectionTimeRange} label="（七）检查起止时间" precision="minute-range" value={introduction.inspection_time_range}
        onChange={value => updateReport('introduction.inspection_time_range', value)} />
      <div className="review-editor-block">
        <div className="review-field__label">（八）检查人员</div>
        <InspectorEditor
          snapshots={toSnapshots(introduction)}
          availableInspectors={availableInspectors}
          loading={inspectorLoading}
          error={inspectorError}
          fieldStates={fieldStates}
          onChange={value => updateReport('introduction.inspector_snapshots', value)}
        />
      </div>
      <ReviewField targetId={REVIEW_TARGET_IDS.inspectionPlace} label="（九）检查地点" type="text" value={introduction.inspection_place}
        onChange={value => updateReport('introduction.inspection_place', value)} />
    </>
  )
}
