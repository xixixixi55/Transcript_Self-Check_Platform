import React from 'react'
import type { InspectionReport } from '@biji/shared/types'
import { Typography } from 'antd'
import { normalizeDataSummary } from '@biji/shared/utils'
import type { PrimarySoftware } from '@biji/shared/types'
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
            onChange={() => undefined} readOnly />
        </div>
        <div className="review-subfield review-primary-software" aria-label="主取证软件">
          <Text strong>主取证软件</Text>
          <span className={`review-primary-software__status ${primarySoftware.confirmation_status === 'unconfirmed' ? 'review-primary-software__status--pending' : ''}`}>
            {primarySoftware.confirmation_status === 'confirmed_by_user' ? '人工确认' :
              primarySoftware.confirmation_status === 'confirmed_by_report' ? '报告自动识别' : '待确认'}
          </span>
          <ReviewField label="主取证软件名称" type="text" value={primarySoftware.name}
            onChange={value => updateReport('inspection.primary_software.name', value)} placeholder="请输入主取证软件名称" />
          <ReviewField label="主取证软件版本" type="text" value={primarySoftware.version}
            onChange={value => updateReport('inspection.primary_software.version', value)} placeholder="请输入主取证软件版本" />
          {primarySoftware.candidates && primarySoftware.candidates.length > 1 ? (
            <Text type="secondary">报告候选存在冲突，请分别确认名称和版本后再导出。</Text>
          ) : null}
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
