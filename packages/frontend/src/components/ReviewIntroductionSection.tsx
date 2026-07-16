import React from 'react'
import type { InspectionReport } from '@biji/shared/types'
import EditableField from './EditableField'
import EvidenceEditor from './EvidenceEditor'
import InspectorEditor from './InspectorEditor'
import { DateTimeField } from './DateTimeField'
import { ReviewField } from './ReviewField'

interface ReviewIntroductionSectionProps {
  introduction: InspectionReport['introduction']
  updateReport: (path: string, value: any) => void
}

export function ReviewIntroductionSection({ introduction, updateReport }: ReviewIntroductionSectionProps) {
  return (
    <>
      <ReviewField label="（一）委托单位" type="text" value={introduction.entrust_unit}
        onChange={value => updateReport('introduction.entrust_unit', value)} />
      <ReviewField label="（二）委托人员" type="text" value={(introduction.entrust_persons || []).join('、')}
        onChange={value => updateReport('introduction.entrust_persons', value.split(/[,，、/]/).map(item => item.trim()).filter(Boolean))} />
      <DateTimeField label="（三）委托时间" precision="date" value={introduction.entrust_time}
        onChange={value => updateReport('introduction.entrust_time', value)} />
      <ReviewField label="（四）案件简要情况" type="textarea" value={introduction.case_summary}
        onChange={value => updateReport('introduction.case_summary', value)} />
      <div className="review-editor-block">
        <div className="review-field__label">（五）检材情况</div>
        <EvidenceEditor items={introduction.evidence_list || []}
          onChange={value => updateReport('introduction.evidence_list', value)} />
      </div>
      <ReviewField label="（六）检查要求" type="textarea" value={introduction.inspection_requirement}
        onChange={value => updateReport('introduction.inspection_requirement', value)} />
      <DateTimeField label="（七）检查起止时间" precision="minute-range" value={introduction.inspection_time_range}
        onChange={value => updateReport('introduction.inspection_time_range', value)} />
      <div className="review-editor-block">
        <div className="review-field__label">（八）检查人员</div>
        <InspectorEditor inspectors={introduction.inspectors || []}
          onChange={value => updateReport('introduction.inspectors', value)} />
      </div>
      <ReviewField label="（九）检查地点" type="text" value={introduction.inspection_place}
        onChange={value => updateReport('introduction.inspection_place', value)} />
    </>
  )
}
