// Layer 11: FE_Components — deferred disc mapping, directory picker and unified export.
import React, { useEffect, useState } from 'react'
import { Alert, Button, Input, Space, message } from 'antd'
import type { CaseLifecycle } from '@biji/shared/types'
import { allPartsDiscMapped, resolveArchiveCompletionStatus } from '@biji/shared/utils'
import { useArchiveCompletion } from '../hooks/useArchiveCompletion'

interface Props {
  lifecycle: CaseLifecycle
  caseId: string
  expectedRevision: number
  parts: { disc_number?: string | null }[] | null
  onCompleted: () => void
}

export function ArchiveCompletionPanel({
  lifecycle, caseId, expectedRevision, parts, onCompleted,
}: Props) {
  const archive = useArchiveCompletion()
  const [firstDiscNumber, setFirstDiscNumber] = useState('')
  const [exportPath, setExportPath] = useState('')
  const [directoryToken, setDirectoryToken] = useState('')
  const status = resolveArchiveCompletionStatus(lifecycle, allPartsDiscMapped(parts))
  useEffect(() => {
    if (archive.error) message.error(archive.error)
  }, [archive.error])

  const submitMapping = async () => {
    const candidate = firstDiscNumber.trim()
    if (!candidate) { message.warning('请输入首个光盘编号。'); return }
    try {
      const result = await archive.mapping(caseId, expectedRevision, candidate)
      message.success(`已按序映射 ${result.parts.length} 个光盘编号。`)
      setFirstDiscNumber('')
      onCompleted()
    } catch { /* error already surfaced via useArchiveCompletion.error */ }
  }

  const pickExportPath = async () => {
    try {
      const result = await archive.chooseDirectory()
      if ('cancelled' in result) return
      setExportPath(result.path)
      setDirectoryToken(result.token)
    } catch { /* error already surfaced via useArchiveCompletion.error */ }
  }

  const runExport = async () => {
    if (!exportPath || !directoryToken) { message.warning('请先选择导出目录。'); return }
    try {
      const result = await archive.exportBundle(caseId, expectedRevision, exportPath, directoryToken)
      message.success(`已导出至：${result.output.export_path}`)
      onCompleted()
    } catch { /* error already surfaced via useArchiveCompletion.error */ }
  }

  if (status === 'disc_pending') {
    return (
      <Alert
        className="case-workbench-page__toolbar"
        type="warning"
        showIcon
        message="待补盘号"
        description="压缩已完成，输入首个光盘编号后系统将按 part 顺序自动生成全序列映射。"
        action={<Space>
          <Input placeholder="如 GP20260731-01" value={firstDiscNumber} onChange={event => setFirstDiscNumber(event.target.value)} />
          <Button type="primary" loading={archive.busy} onClick={() => { void submitMapping() }}>提交盘号映射</Button>
        </Space>}
      />
    )
  }

  if (status === 'archive_complete' || status === 'exported') {
    return (
      <Alert
        className="case-workbench-page__toolbar"
        type="success"
        showIcon
        message={status === 'exported' ? '已导出' : '归档完成'}
        description={status === 'exported'
          ? '统一导出已完成，可再次导出获取最新 Word、RAR 与校验 HTML。'
          : exportPath ? `导出目录：${exportPath}` : '全部 RAR、MD5 与盘号已对应完成，请选择导出目录后开始导出。'}
        action={<Space>
          <Button loading={archive.busy} onClick={() => { void pickExportPath() }}>选择导出目录</Button>
          <Button type="primary" loading={archive.busy} onClick={() => { void runExport() }}>{status === 'exported' ? '再次导出' : '开始导出'}</Button>
        </Space>}
      />
    )
  }

  return null
}
