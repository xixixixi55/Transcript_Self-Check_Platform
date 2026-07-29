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
  const draftRecovery = draft.status === 'failed'
  const draftConflict = draft.status === 'conflict'
  const recovery = draftRecovery || sharedDefaults.status === 'failed'
  const conflict = draftConflict || sharedDefaults.status === 'conflict'
  const draftSavedDefaultsFailed = draft.status === 'saved' && sharedDefaults.status === 'failed'
  const draftSavedDefaultsConflict = draft.status === 'saved' && sharedDefaults.status === 'conflict'
  const draftAction = draftRecovery || draftConflict
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
          message={draftSavedDefaultsFailed ? '草稿已保存，共享默认值更新失败。' : draftSavedDefaultsConflict ? '草稿已保存，共享默认值版本冲突。' : conflict ? '案件版本发生冲突，当前输入未覆盖服务端新版本。' : '保存未完成，当前页面输入仍保留。'}
          description={draftSavedDefaultsFailed || draftSavedDefaultsConflict ? '当前案件已经保存；请重新修改相关共享字段后，再通过“保存修改”重试。' : conflict ? '请加载服务端版本后重新编辑，或由明确的后续操作解决冲突。' : '请检查后端连接后重试。'}
          action={draftAction ? <Space><Button size="small" onClick={onRetry} disabled={!draftRecovery}>重试保存</Button><Button size="small" onClick={onLoadServer}>加载服务端版本</Button></Space> : undefined}
        />
      )}
    </div>
  )
}
