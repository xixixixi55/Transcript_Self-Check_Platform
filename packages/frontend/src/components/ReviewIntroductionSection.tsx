import React from 'react'
import type { FieldState, InspectorLibraryRecord, InspectionReport, InspectorSnapshot } from '@biji/shared/types'
import { Alert } from 'antd'
import EditableField from './EditableField'
import EvidenceEditor from './EvidenceEditor'
import InspectorEditor from './InspectorEditor'
import { DateTimeField } from './DateTimeField'
import { ReviewField } from './ReviewField'

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
      <ReviewField label="委托单位前缀（共享默认值）" type="text" value={introduction.entrust_unit_prefix || ''}
        onChange={value => updateReport('introduction.entrust_unit_prefix', value)} />
      <ReviewField label="（一）委托单位" type="text" value={introduction.entrust_unit}
        onChange={value => updateReport('introduction.entrust_unit', value)} />
      <ReviewField label="（二）委托人员" type="text" value={(introduction.entrust_persons || []).join('、')}
        onChange={value => updateReport('introduction.entrust_persons', value.split(/[,，、/]/).map(item => item.trim()).filter(Boolean))} />
      <DateTimeField label="（三）委托时间" precision="date" value={introduction.entrust_time}
        onChange={value => updateReport('introduction.entrust_time', value)} />
      <ReviewField label="（四）案件简要情况" type="textarea" value={introduction.case_summary}
        onChange={value => updateReport('introduction.case_summary', value)} />
      <Alert
        type={hasTrailingWhitespace ? 'warning' : 'info'}
        showIcon
        message="案件简要情况由报告自动解析，可能不准确，请人工核对。"
        description={hasTrailingWhitespace
          ? '当前内容末尾存在多余回车、空格或制表符，请检查并删除。'
          : undefined}
      />
      <div className="review-editor-block">
        <div className="review-field__label">（五）检材情况</div>
        <EvidenceEditor items={introduction.evidence_list || []}
          fieldStates={fieldStates}
          onChange={value => updateReport('introduction.evidence_list', value)} />
      </div>
      <ReviewField label="（六）检查要求" type="textarea" value={introduction.inspection_requirement}
        onChange={value => updateReport('introduction.inspection_requirement', value)} />
      <DateTimeField label="（七）检查起止时间" precision="minute-range" value={introduction.inspection_time_range}
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
      <ReviewField label="（九）检查地点" type="text" value={introduction.inspection_place}
        onChange={value => updateReport('introduction.inspection_place', value)} />
    </>
  )
}
