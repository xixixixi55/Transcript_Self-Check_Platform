// 第 11 层：FE_Components — 陌生报告字段候选的显式确认界面。
import React, { useEffect, useMemo, useState } from 'react'
import { Alert, Input, Modal, Select, Space, Tag, Typography } from 'antd'
import { SafetyCertificateOutlined } from '@ant-design/icons'
import type { ReportFieldCandidate, ReportProfileDiscovery } from '@biji/shared/types'

const { Text, Title } = Typography

const FIELD_LABELS: Record<string, string> = {
  'case.case_name': '案件名称',
  'case.case_number': '案件编号',
  'case.entrust_unit': '送检单位',
  'case.entrust_persons': '送检人',
  'case.case_summary': '案件简要情况',
  'case.created_at': '案件创建时间',
  'case.reported_at': '报告时间',
  'software.name': '主取证软件名称',
  'software.version': '主取证软件版本',
  'inspection.hardware_device': '取证硬件',
  'material.evidence_number': '检材编号',
  'material.name': '设备名称',
  'material.model': '设备型号',
  'material.holder_name': '持有人',
  'material.imei1': 'IMEI1',
  'material.imei2': 'IMEI2',
  'material.serial_number': '序列号',
  'material.acquisition_started_at': '取证开始时间',
  'material.acquisition_ended_at': '取证结束时间',
  'material.type': '检材类型',
}

interface Props {
  discovery: ReportProfileDiscovery | null
  confirming?: boolean
  onCancel: () => void
  onConfirm: (candidateIds: string[], displayName: string) => void
}

function optionText(candidate: ReportFieldCandidate): string {
  const preview = candidate.preview_values.filter(Boolean).join('；') || '空值'
  return preview.length > 72 ? `${preview.slice(0, 72)}…` : preview
}

export function ReportProfileDiscoveryModal({
  discovery, confirming = false, onCancel, onConfirm,
}: Props) {
  const [displayName, setDisplayName] = useState('')
  const [selections, setSelections] = useState<Record<string, string>>({})
  useEffect(() => {
    setDisplayName('')
    setSelections({})
  }, [discovery?.discovery_token])

  const groups = useMemo(() => {
    const result = new Map<string, ReportFieldCandidate[]>()
    for (const candidate of discovery?.candidates ?? []) {
      result.set(candidate.canonical_field, [
        ...(result.get(candidate.canonical_field) ?? []), candidate,
      ])
    }
    return [...result.entries()].sort(
      ([left], [right]) => (FIELD_LABELS[left] || left)
        .localeCompare(FIELD_LABELS[right] || right, 'zh-CN'),
    )
  }, [discovery])
  const selectedIds = Object.values(selections).filter(Boolean)
  const canConfirm = displayName.trim().length > 0 && selectedIds.length > 0

  return (
    <Modal
      open={Boolean(discovery)}
      className="report-profile-discovery"
      width={720}
      title={null}
      okText="确认映射并创建案件"
      cancelText="取消"
      confirmLoading={confirming}
      okButtonProps={{ disabled: !canConfirm }}
      onCancel={onCancel}
      onOk={() => onConfirm(selectedIds, displayName.trim())}
      destroyOnHidden
    >
      <div className="report-profile-discovery__heading">
        <span className="report-profile-discovery__icon" aria-hidden="true">
          <SafetyCertificateOutlined />
        </span>
        <div>
          <Title level={3}>确认陌生报告字段</Title>
          <Text>系统只发现了候选关系。请确认后再创建案件；未选择的字段会留空待审核。</Text>
        </div>
      </div>
      <Alert
        type="info"
        showIcon
        message="此配置只保存字段位置和结构指纹，不保存本案字段值。"
      />
      <label className="report-profile-discovery__name">
        <span>配置名称</span>
        <Input
          value={displayName}
          maxLength={120}
          placeholder="例如：某厂商网页版报告 2026"
          onChange={event => setDisplayName(event.target.value)}
        />
      </label>
      <div className="report-profile-discovery__fields">
        {groups.map(([field, candidates]) => (
          <div className="report-profile-discovery__field" key={field}>
            <div className="report-profile-discovery__field-label">
              <span>{FIELD_LABELS[field] || field}</span>
              <Tag bordered={false}>{Math.round(candidates[0].confidence * 100)}% 候选</Tag>
            </div>
            <Select
              allowClear
              value={selections[field]}
              placeholder="不映射"
              aria-label={`选择${FIELD_LABELS[field] || field}来源`}
              onChange={value => setSelections(current => ({ ...current, [field]: value }))}
              options={candidates.map(candidate => ({
                value: candidate.candidate_id,
                label: optionText(candidate),
                title: `${candidate.source_file} · ${candidate.json_path}`,
              }))}
            />
            <Text type="secondary">
              {(() => {
                const selected = candidates.find(
                  candidate => candidate.candidate_id === selections[field],
                )
                return selected
                  ? `${selected.source_file} · ${selected.json_path}`
                  : `${candidates.length} 个候选来源，选择后显示字段位置`
              })()}
            </Text>
          </div>
        ))}
      </div>
    </Modal>
  )
}
