// Layer 11: FE_Components — approved, versioned template selection.
import React, { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Card, Spin, Tag } from 'antd'
import { TEMPLATE_APPROVAL_STATUS } from '@biji/shared/constants'
import type {
  TemplateSelectionImpact,
  TemplateVersion,
  TemplateVersionRef,
} from '@biji/shared/types'

interface Props {
  templates: TemplateVersion[]
  currentTemplateRef: TemplateVersionRef | null
  loading: boolean
  saving: boolean
  disabled: boolean
  errorCode: string | null
  impact: TemplateSelectionImpact | null
  onSelect: (templateRef: TemplateVersionRef) => Promise<boolean>
}

const errorMessages: Record<string, string> = {
  TEMPLATE_UNKNOWN: '所选模板版本不存在，请刷新模板列表。',
  TEMPLATE_NOT_APPROVED: '所选模板版本尚未审核通过，不能用于案件。',
  TEMPLATE_ASSET_MISSING: '所选模板资产不可用，请联系管理员。',
  TEMPLATE_FINGERPRINT_MISMATCH: '所选模板指纹校验失败，不能用于案件。',
  TEMPLATE_RULE_VALIDATION_FAILED: '所选模板未通过结构校验，不能用于案件。',
  TEMPLATE_REGISTRY_LOAD_FAILED: '已审核模板列表暂时无法加载，请稍后重试。',
  TEMPLATE_SELECTION_FAILED: '案件模板未保存，请稍后重试。',
  TEMPLATE_SELECTION_IMPACT_INVALID: '模板切换结果未通过安全校验，案件未接受该结果。',
  TEMPLATE_SELECTION_READ_ONLY: '当前页面没有有效编辑租约，不能修改案件模板。',
  REVISION_CONFLICT: '案件已被其他会话修改，请重新加载后再选择模板。',
  LEASE_CONFLICT: '案件当前由其他编辑会话占用，不能修改模板。',
  LEASE_NOT_ACTIVE: '当前编辑租约已失效，请重新获取后再选择模板。',
  LEASE_EXPIRED: '当前编辑租约已过期，请重新获取后再选择模板。',
  LEASE_TAKEOVER_REQUIRED: '当前编辑租约需要确认接管后才能修改模板。',
}

function refKey(value: TemplateVersionRef): string {
  return JSON.stringify([value.template_id, value.version])
}

export function TemplateSelector({
  templates, currentTemplateRef, loading, saving, disabled, errorCode, impact, onSelect,
}: Props) {
  const approved = useMemo(
    () => templates.filter(item => item.approval_record.status === TEMPLATE_APPROVAL_STATUS.APPROVED),
    [templates],
  )
  const currentKey = currentTemplateRef ? refKey(currentTemplateRef) : ''
  const [selectedKey, setSelectedKey] = useState(currentKey)
  useEffect(() => { setSelectedKey(currentKey) }, [currentKey])
  const selected = approved.find(item => refKey(item.template_ref) === selectedKey) || null

  return (
    <Card className="case-workbench-page__toolbar" title="案件 Word 模板" size="small">
      <p>只可选择已注册且审核通过的版本；案件仅保存模板 ID 和版本。</p>
      {loading ? <Spin size="small" aria-label="正在加载已审核模板" /> : (
        <label>
          <span>已审核模板版本</span>
          <select
            aria-label="已审核模板版本"
            value={selectedKey}
            disabled={disabled || saving || approved.length === 0}
            onChange={event => setSelectedKey(event.target.value)}
          >
            <option value="">请选择模板</option>
            {approved.map(template => (
              <option key={refKey(template.template_ref)} value={refKey(template.template_ref)}>
                {template.display_name} · {template.template_ref.template_id} · {template.template_ref.version}
              </option>
            ))}
          </select>
        </label>
      )}
      {selected && (
        <div>
          <Tag color="success">已审核</Tag>
          <div>模板 ID：{selected.template_ref.template_id}</div>
          <div>版本：{selected.template_ref.version}</div>
          <div>验收摘要：{selected.approval_record.acceptance_summary}</div>
        </div>
      )}
      {!loading && approved.length === 0 && (
        <Alert type="warning" showIcon message="当前没有可选择的已审核模板版本。" />
      )}
      {currentTemplateRef && !approved.some(item => refKey(item.template_ref) === currentKey) && (
        <Alert type="warning" showIcon message="案件当前引用的模板版本不在可用列表中，请选择新的已审核版本。" />
      )}
      {errorCode && <Alert type="error" showIcon message={errorMessages[errorCode] || '模板操作未完成。'} />}
      {impact && (
        <Alert
          type="warning"
          showIcon
          message="案件模板已更新，先前生成的 Word 已失效。"
          description="下次导出将重新校验所选模板；RAR、Manifest、归档任务和光盘映射保持不变。"
        />
      )}
      <Button
        type="primary"
        loading={saving}
        disabled={disabled || !selected || selectedKey === currentKey}
        onClick={() => { if (selected) void onSelect(selected.template_ref) }}
      >
        应用模板版本
      </Button>
    </Card>
  )
}
