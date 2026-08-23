import React from 'react'
import type { FieldState, InspectorLibraryRecord, InspectionReport, InspectorSnapshot } from '@biji/shared/types'
import { Alert, Button } from 'antd'
import EvidenceEditor from './EvidenceEditor'
import InspectorEditor from './InspectorEditor'
import { DateTimeField } from './DateTimeField'
import { ReviewField } from './ReviewField'
import { EVIDENCE_COMPLETENESS_FIELD_PATH, REVIEW_TARGET_IDS } from '../hooks/useReviewChecklist'

interface ReviewIntroductionSectionProps {
  introduction: InspectionReport['introduction']
  updateReport: (path: string, value: any) => void
  availableInspectors: InspectorLibraryRecord[]
  inspectorLoading: boolean
  inspectorError: string | null
  fieldStates?: Record<string, FieldState>
  onEvidenceCompletenessChange: (confirmed: boolean) => void
}

const ENTRUST_PERSON_SEPARATOR = /[、,，;；/／|｜\r\n]+/

export function normalizeEntrustPersons(value: string | string[]): string[] {
  const values = Array.isArray(value) ? value : [value]
  return values.flatMap(item => item.split(ENTRUST_PERSON_SEPARATOR))
    .map(item => item.trim())
    .filter(Boolean)
}

function formatEntrustPersons(value: string[]): string {
  return normalizeEntrustPersons(value).join('、')
}

function toSnapshots(introduction: InspectionReport['introduction']): InspectorSnapshot[] {
  if (Array.isArray(introduction.inspector_snapshots)) return introduction.inspector_snapshots
  return (introduction.inspectors || []).map(inspector => ({
    name: inspector.name,
    unit: inspector.unit,
    position: inspector.position,
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
  onEvidenceCompletenessChange,
}: ReviewIntroductionSectionProps) {
  const hasTrailingWhitespace = /[ \t\r\n]+$/.test(introduction.case_summary || '')
  const evidenceCompletenessConfirmed = fieldStates?.[EVIDENCE_COMPLETENESS_FIELD_PATH]?.confirmation === 'confirmed'
  return (
    <>
      <div className="review-field-row review-field-row--entrust-unit">
        <ReviewField label="委托单位前缀" type="text" value={introduction.entrust_unit_prefix || ''}
          onChange={value => updateReport('introduction.entrust_unit_prefix', value)} />
        <ReviewField targetId={REVIEW_TARGET_IDS.entrustUnit} label="（一）委托单位" type="text" value={introduction.entrust_unit}
          onChange={value => updateReport('introduction.entrust_unit', value)} />
      </div>
      <ReviewField targetId={REVIEW_TARGET_IDS.entrustPersons} label="（二）委托人员" type="text" value={formatEntrustPersons(introduction.entrust_persons || [])}
        onChange={value => updateReport('introduction.entrust_persons', normalizeEntrustPersons(value))} />
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
      <div id={REVIEW_TARGET_IDS.evidenceCompleteness} className="review-editor-block review-navigation-target" tabIndex={-1}>
        <div className="review-evidence-heading">
          <div className="review-field__label">（五）检材情况</div>
          {!evidenceCompletenessConfirmed && (
            <Button className="review-evidence-confirmation" danger type="primary" size="small"
              onClick={() => onEvidenceCompletenessChange(true)}>
              请确认检材是否完整？
            </Button>
          )}
        </div>
        <EvidenceEditor items={introduction.evidence_list || []}
          fieldStates={fieldStates}
          onChange={value => {
            updateReport('introduction.evidence_list', value)
            onEvidenceCompletenessChange(false)
          }} />
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
