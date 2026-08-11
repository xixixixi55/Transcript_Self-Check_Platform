// Layer 11: FE_Components — unified first-disc input, deferred mapping and export.
import React, { useEffect, useState } from 'react'
import { Alert, Button, Input, Space, message } from 'antd'
import type { CaseLifecycle } from '@biji/shared/types'
import {
  resolveArchiveCompletionStatusForParts,
  useArchiveCompletion,
} from '../hooks/useArchiveCompletion'
import { WordDownloadNameDialog } from './WordDownloadNameDialog'

interface Props {
  lifecycle: CaseLifecycle
  caseId: string
  expectedRevision: number
  planRowRevision: number | null
  parts: { disc_number?: string | null; size_bytes?: number | null }[] | null
  firstDiscNumber: string
  onFirstDiscNumberChange: (value: string) => void
  readOnly?: boolean
  defaultWordName?: string
  onCompleted: () => void
}

export function ArchiveCompletionPanel({
  lifecycle, caseId, expectedRevision, planRowRevision, parts,
  firstDiscNumber, onFirstDiscNumberChange,
  readOnly = false, defaultWordName, onCompleted,
}: Props) {
  const archive = useArchiveCompletion()
  const persistedFirstDiscNumber = String(parts?.[0]?.disc_number || '').trim()
  const effectiveFirstDiscNumber = persistedFirstDiscNumber || firstDiscNumber
  const [mappingDiscNumber, setMappingDiscNumber] = useState(effectiveFirstDiscNumber)
  const [mappingPlanRowRevision, setMappingPlanRowRevision] = useState(planRowRevision)
  const [nameDialogOpen, setNameDialogOpen] = useState(false)
  const status = resolveArchiveCompletionStatusForParts(lifecycle, parts)
  useEffect(() => {
    if (archive.error) message.error(archive.error)
  }, [archive.error])
  useEffect(() => {
    setMappingDiscNumber(effectiveFirstDiscNumber)
  }, [effectiveFirstDiscNumber])
  useEffect(() => {
    setMappingPlanRowRevision(planRowRevision)
  }, [planRowRevision])

  const submitMapping = async () => {
    if (readOnly) { message.warning('当前页面为只读，不能提交光盘编号。'); return }
    if (mappingPlanRowRevision === null) { message.warning('归档计划版本尚未加载，请刷新后重试。'); return }
    const candidate = mappingDiscNumber.trim()
    if (!candidate) { message.warning('请输入首个光盘编号。'); return }
    try {
      const result = await archive.mapping(
        caseId, expectedRevision, mappingPlanRowRevision, candidate,
      )
      setMappingPlanRowRevision(result.plan_row_revision)
      onFirstDiscNumberChange(candidate)
      message.success(`已按序映射 ${result.parts.length} 个光盘编号。`)
      onCompleted()
    } catch { /* error already surfaced via useArchiveCompletion.error */ }
  }

  const runExport = () => {
    setNameDialogOpen(true)
  }

  const confirmExportName = async (wordFileName: string) => {
    setNameDialogOpen(false)
    try {
      // Directory grants are one-use and consumed by the export; always pick a
      // fresh directory so re-export never reuses a spent token.
      const chosen = await archive.chooseDirectory()
      if ('cancelled' in chosen) return
      const result = await archive.exportBundle(
        caseId, expectedRevision, chosen.path, chosen.token, wordFileName,
        parts,
      )
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
          <Input aria-label="首个光盘编号" placeholder="如 GP20260731-01" value={mappingDiscNumber}
            disabled={readOnly} onChange={event => setMappingDiscNumber(event.target.value)} />
          <Button type="primary" loading={archive.busy} disabled={readOnly}
            onClick={() => { void submitMapping() }}>提交盘号映射</Button>
        </Space>}
      />
    )
  }

  if (status === 'archive_complete' || status === 'exported') {
    return (
      <>
        <Alert
          className="case-workbench-page__toolbar"
          type="success"
          showIcon
          message={status === 'exported' ? '已导出' : '归档完成'}
          description={status === 'exported'
            ? '统一导出已完成，可再次导出获取最新 Word、RAR 与校验截图。'
            : '全部 RAR、MD5 与盘号已对应完成，可开始导出。'}
          action={<Space>
            <Input aria-label="首个光盘编号" placeholder="如 GP20260731-01" value={mappingDiscNumber}
              disabled={readOnly} onChange={event => setMappingDiscNumber(event.target.value)} />
            <Button loading={archive.busy} disabled={readOnly}
              onClick={() => { void submitMapping() }}>更新盘号映射</Button>
            <Button type="primary" loading={archive.busy} onClick={() => { runExport() }}>{status === 'exported' ? '再次导出' : '开始导出'}</Button>
          </Space>}
        />
        <WordDownloadNameDialog
          open={nameDialogOpen}
          documentNumber={defaultWordName}
          exporting={archive.busy}
          onCancel={() => setNameDialogOpen(false)}
          onConfirm={downloadName => { void confirmExportName(downloadName) }}
        />
      </>
    )
  }

  return (
    <Alert
      className="case-workbench-page__toolbar"
      type="info"
      showIcon
      message="光盘编号"
      description={status === 'compressing'
        ? '压缩正在后台进行；现在仍可填写首个光盘编号，压缩完成后将沿用该编号。'
        : '可在开始压缩前填写首个光盘编号；修改会随案件草稿自动保存。'}
      action={<Input aria-label="首个光盘编号" placeholder="如 GP20260731-01" value={firstDiscNumber}
        disabled={readOnly} onChange={event => onFirstDiscNumberChange(event.target.value)} />}
    />
  )
}
