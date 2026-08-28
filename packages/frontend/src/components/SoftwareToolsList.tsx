// 第 11 层：FE_Components — 软件工具列表
// REQ-017: 展示软件工具列表，名称和版本号均可编辑
import React from 'react'
import { Button, Space } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import EditableField from './EditableField'
import type { PrimarySoftware, SoftwareItem } from '@biji/shared/types'
import { REVIEW_TARGET_IDS } from '../hooks/useReviewChecklist'

interface Props {
  tools: SoftwareItem[]
  onChange: (tools: SoftwareItem[]) => void
  primarySoftware?: PrimarySoftware
  onPrimarySoftwareChange?: (field: 'name' | 'version', value: string) => void
  readOnly?: boolean
}

function isPrimaryTool(tool: SoftwareItem, primarySoftware: PrimarySoftware): boolean {
  const category = (tool as SoftwareItem & { category?: string }).category
  return category === 'main_forensic'
    || Boolean(primarySoftware.name && primarySoftware.version
      && tool.name === primarySoftware.name && tool.version === primarySoftware.version)
}

export default function SoftwareToolsList({
  tools,
  onChange,
  primarySoftware,
  onPrimarySoftwareChange,
  readOnly = false,
}: Props) {
  const update = (idx: number, field: keyof SoftwareItem, val: string) => {
    onChange(tools.map((t, i) => i === idx ? { ...t, [field]: val } : t))
  }

  const add = () => onChange([...tools, { name: '', version: '' }])
  const remove = (idx: number) => onChange(tools.filter((_, i) => i !== idx))
  const visibleTools = tools
    .map((tool, index) => ({ tool, index }))
    .filter(({ tool }) => !primarySoftware || !isPrimaryTool(tool, primarySoftware))
  const primaryStatus = primarySoftware?.confirmation_status === 'confirmed_by_user'
    ? '人工确认'
    : primarySoftware?.confirmation_status === 'confirmed_by_report'
      ? '报告自动识别'
      : '待确认'

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={4}>
      {primarySoftware && onPrimarySoftwareChange ? (
        <div id={REVIEW_TARGET_IDS.primarySoftwareStatus}
          className="software-tool-row software-tool-row--primary review-navigation-target"
          tabIndex={-1} aria-label="主取证软件">
          <div className="software-tool-row__heading">
            <strong>主取证软件</strong>
            <span className={`software-tool-row__status ${primarySoftware.confirmation_status === 'unconfirmed' ? 'software-tool-row__status--pending' : ''}`}>
              {primaryStatus}
            </span>
          </div>
          <div className="software-tool-row__fields">
            <div id={REVIEW_TARGET_IDS.primarySoftwareName}
              className="software-tool-row__field review-navigation-target" tabIndex={-1}>
              <span>名称</span>
              <EditableField type="text" value={primarySoftware.name}
                onChange={value => onPrimarySoftwareChange('name', value)}
                placeholder="请输入主取证软件名称" />
            </div>
            <div id={REVIEW_TARGET_IDS.primarySoftwareVersion}
              className="software-tool-row__field review-navigation-target" tabIndex={-1}>
              <span>版本号</span>
              <EditableField type="text" value={primarySoftware.version}
                onChange={value => onPrimarySoftwareChange('version', value)}
                placeholder="请输入主取证软件版本" />
            </div>
          </div>
          {primarySoftware.candidates.length > 1 ? (
            <span className="software-tool-row__hint">报告候选存在冲突，请确认名称和版本后再导出。</span>
          ) : null}
        </div>
      ) : null}
      {visibleTools.map(({ tool, index }) => (
        <div id={REVIEW_TARGET_IDS.softwareTool(index)}
          className="software-tool-row review-navigation-target" tabIndex={-1}
          key={index}>
          <EditableField type="text" value={tool.name}
            onChange={v => update(index, 'name', v)}
            placeholder="软件名称" />
          <span>版本号</span>
          <EditableField type="text" value={tool.version}
            onChange={v => update(index, 'version', v)}
            placeholder="版本号" />
          <Button type="text" danger size="small" icon={<DeleteOutlined />}
            onClick={() => remove(index)} />
        </div>
      ))}
      {!readOnly && <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={add}>
        添加软件工具
      </Button>}
    </Space>
  )
}
