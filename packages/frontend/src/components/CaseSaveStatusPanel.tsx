// Layer 11: FE_Components — distinct draft/default save states and recovery actions.
import React from 'react'
import { Alert, Button, Space } from 'antd'
import type { AutosaveViewState } from '../hooks/useCaseDraftAutosave'

const LABELS = {
  idle: '尚未保存', saving: '保存中', saved: '已保存', failed: '保存失败', conflict: '版本冲突', not_changed: '本次未更新',
} as const

function text(state: AutosaveViewState) {
  return `${LABELS[state.status]}${state.revision == null ? '' : `（revision ${state.revision}）`}`
}
interface Props {
  draft: AutosaveViewState
  sharedDefaults: AutosaveViewState
  onRetry: () => void
  onLoadServer: () => void
}

export function CaseSaveStatusPanel({ draft, sharedDefaults, onRetry, onLoadServer }: Props) {
  const recovery = draft.status === 'failed' || sharedDefaults.status === 'failed'
  const conflict = draft.status === 'conflict' || sharedDefaults.status === 'conflict'
  return (
    <div className="case-save-status-panel" aria-live="polite">
      <Space wrap>
        <span>案件草稿：{text(draft)}</span>
        <span>共享默认值：{text(sharedDefaults)}</span>
      </Space>
      {(recovery || conflict) && (
        <Alert
          type={conflict ? 'warning' : 'error'}
          showIcon
          message={conflict ? '案件版本发生冲突，当前输入未覆盖服务端新版本。' : '保存未完成，当前页面输入仍保留。'}
          description={conflict ? '请加载服务端版本后重新编辑，或由明确的后续操作解决冲突。' : '请检查后端连接后重试。'}
          action={<Space><Button size="small" onClick={onRetry} disabled={!recovery}>重试保存</Button><Button size="small" onClick={onLoadServer}>加载服务端版本</Button></Space>}
        />
      )}
    </div>
  )
}
