import React from 'react'
import type { InspectionReport } from '@biji/shared/types'
import { Typography } from 'antd'
import { normalizeDataSummary } from '@biji/shared/utils'
import EditableField from './EditableField'
import ProcessStepsEditor from './ProcessStepsEditor'
import SoftwareToolsList from './SoftwareToolsList'
import { ReviewField } from './ReviewField'

const { Text } = Typography

interface ReviewInspectionSectionProps {
  inspection: InspectionReport['inspection']
  updateReport: (path: string, value: any) => void
  deviceOptions: { label: string; value: string }[]
}

export function ReviewInspectionSection({ inspection, updateReport, deviceOptions }: ReviewInspectionSectionProps) {
  const resultFields: [string, keyof InspectionReport['inspection']['result']][] = [
    ['检材编号', 'evidence_number'], ['软件名称', 'software_name'], ['软件版本', 'software_version'],
    ['数据摘要', 'data_summary'], ['RAR 文件名', 'rar_filename'], ['MD5 哈希', 'md5_hash'], ['文件大小', 'file_size'],
  ]

  return (
    <>
      <ReviewField label="（一）检查方法" type="textarea" value={inspection.method}
        onChange={value => updateReport('inspection.method', value)} />
      <div className="review-editor-block">
        <div className="review-field__label">（二）检查设备</div>
        <div className="review-subfield">
          <Text strong>1、硬件设备</Text>
          <EditableField type="select" value={inspection.hardware_device}
            onChange={value => updateReport('inspection.hardware_device', value)} options={deviceOptions} />
        </div>
        <div className="review-subfield">
          <Text strong>{inspection.software_tools?.length ? `2-${inspection.software_tools.length + 1}、软件工具` : '2、软件工具'}</Text>
          <SoftwareToolsList tools={inspection.software_tools || []}
            onChange={value => updateReport('inspection.software_tools', value)} />
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
          <div className="review-result-field" key={key}>
            <Text type="secondary">{label}</Text>
            <EditableField type="text" value={key === 'data_summary'
              ? normalizeDataSummary((inspection.result as any)?.[key])
              : String((inspection.result as any)?.[key] || '')}
              onChange={value => updateReport(`inspection.result.${key}`,
                key === 'data_summary' ? normalizeDataSummary(value) : value)} />
          </div>
        ))}
      </div>
    </>
  )
}
