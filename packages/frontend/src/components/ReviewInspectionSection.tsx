import React from 'react'
import type { InspectionReport } from '@biji/shared/types'
import { Typography } from 'antd'
import { hashAlgorithmLabel, normalizeDataSummary } from '@biji/shared/utils'
import type { PrimarySoftware } from '@biji/shared/types'
import EditableField from './EditableField'
import ProcessStepsEditor from './ProcessStepsEditor'
import SoftwareToolsList from './SoftwareToolsList'
import { ReviewField } from './ReviewField'
import { REVIEW_TARGET_IDS } from '../hooks/useReviewChecklist'

const { Text } = Typography

interface ReviewInspectionSectionProps {
  inspection: InspectionReport['inspection']
  updateReport: (path: string, value: any) => void
  deviceOptions: { label: string; value: string }[]
}

export function ReviewInspectionSection({ inspection, updateReport, deviceOptions }: ReviewInspectionSectionProps) {
  const primarySoftware: PrimarySoftware = inspection.primary_software || {
    name: inspection.result?.software_name || '',
    version: inspection.result?.software_version || '',
    display_name: '',
    confirmation_status: 'unconfirmed',
    provenance: [],
    candidates: [],
  }
  const resultFields: [string, keyof InspectionReport['inspection']['result']][] = [
    ['检材编号', 'evidence_number'],
    ['数据摘要', 'data_summary'], ['RAR 文件名', 'rar_filename'],
    [`${hashAlgorithmLabel(inspection.result?.hash_algorithm)} 哈希`, 'md5_hash'],
    ['文件大小', 'file_size'],
  ]

  return (
    <>
      <ReviewField targetId={REVIEW_TARGET_IDS.inspectionMethod} label="（一）检查方法" type="textarea" value={inspection.method}
        onChange={value => updateReport('inspection.method', value)} />
      <div className="review-editor-block">
        <div className="review-field__label">（二）检查设备</div>
        <div id={REVIEW_TARGET_IDS.hardwareDevice} className="review-subfield review-navigation-target" tabIndex={-1}>
          <Text strong>1、硬件设备</Text>
          <EditableField type="select" value={inspection.hardware_device}
            onChange={value => updateReport('inspection.hardware_device', value)} options={deviceOptions} />
        </div>
        <div className="review-subfield">
          <Text strong>2、软件工具</Text>
          <SoftwareToolsList
            tools={inspection.software_tools || []}
            primarySoftware={primarySoftware}
            onPrimarySoftwareChange={(field, value) =>
              updateReport(`inspection.primary_software.${field}`, value)}
            onChange={() => undefined}
            readOnly
          />
        </div>
      </div>
      <div className="review-editor-block">
        <div className="review-field__label">（三）检查过程</div>
        <ProcessStepsEditor steps={inspection.process_steps || []}
          onChange={value => updateReport('inspection.process_steps', value)} />
      </div>
      <div className="review-editor-block review-result-block">
        <div className="review-field__label">（四）检查结果</div>
        {resultFields.map(([label, key]) => (
          <div id={REVIEW_TARGET_IDS.result(key)} className="review-result-field review-navigation-target" tabIndex={-1} key={key}>
            <Text type="secondary">{label}</Text>
            <EditableField type="text" value={key === 'data_summary'
              ? normalizeDataSummary((inspection.result as any)?.[key])
              : key === 'md5_hash'
                ? String((inspection.result as any)?.[key] || '').toUpperCase()
                : String((inspection.result as any)?.[key] || '')}
              onChange={value => updateReport(`inspection.result.${key}`,
                key === 'data_summary' ? normalizeDataSummary(value)
                  : key === 'md5_hash' ? value.toUpperCase() : value)} />
          </div>
        ))}
      </div>
    </>
  )
}
