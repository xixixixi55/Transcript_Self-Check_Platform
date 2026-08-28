// 第 11 层：FE_Components — 受控替换目录来源，不回显路径。
import React, { useState } from 'react'
import { Alert, Button, Input, Space } from 'antd'
import { SourceStatusBadge } from './SourceStatusBadge'
import { resolveWorkbenchError } from '../hooks'

interface Props {
  required: boolean
  onReselect: (sourcePath: string) => Promise<boolean>
}

export function SourceReselectionPanel({ required, onReselect }: Props) {
  const [sourcePath, setSourcePath] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  if (!required) return null
  const choose = async () => {
    if (!sourcePath.trim()) return
    setBusy(true); setError(null)
    try { if (!await onReselect(sourcePath.trim())) setError('来源重新登记未完成，请重试。') }
    catch (failure) { setError(resolveWorkbenchError(failure).message) }
    finally { setBusy(false) }
  }
  return (
    <Alert
      type="warning"
      showIcon
      message={<Space><SourceStatusBadge status="requires_reselection" />来源已失效，请重新登记报告目录。</Space>}
      description={<Space direction="vertical" style={{ width: '100%' }}>
        <Input aria-label="重新选择报告目录路径" value={sourcePath} onChange={event => setSourcePath(event.target.value)} placeholder="粘贴报告目录的本机绝对路径" />
        <Button loading={busy} onClick={() => { void choose() }}>重新登记来源目录</Button>
        {error && <span className="review-field__error">{error}</span>}
      </Space>}
    />
  )
}
