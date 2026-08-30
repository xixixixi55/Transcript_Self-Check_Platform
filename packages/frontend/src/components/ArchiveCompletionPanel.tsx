// 第 11 层：FE_Components — 统一的首张光盘输入、延迟映射与导出。
import React, { useEffect, useState } from 'react'
import { Alert, Button, Input, Space, message } from 'antd'
import type { ArchiveMedium, CaseLifecycle } from '@biji/shared/types'
import {
  resolveArchiveCompletionStatusForParts,
  useArchiveCompletion,
} from '../hooks/useArchiveCompletion'
import { WordDownloadNameDialog } from './WordDownloadNameDialog'
import { REVIEW_TARGET_IDS } from '../hooks/useReviewChecklist'

interface Props {
  lifecycle: CaseLifecycle
  caseId: string
  expectedRevision: number
  planRowRevision: number | null
  archiveMedium?: ArchiveMedium | null
  parts: { disc_number?: string | null; size_bytes?: number | null }[] | null
  firstDiscNumber: string
  onFirstDiscNumberChange: (value: string) => void
  readOnly?: boolean
  defaultWordName?: string
  onCompleted: () => void
}

export function ArchiveCompletionPanel({
  lifecycle, caseId, expectedRevision, planRowRevision, parts,
  archiveMedium = 'optical_disc',
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
  const hardDrive = archiveMedium === 'hard_drive'
  const mediumLabel = hardDrive ? '硬盘' : archiveMedium === 'optical_disc' ? '光盘' : '介质'
  const numberLabel = hardDrive ? '硬盘编号' : archiveMedium === 'optical_disc' ? '首个光盘编号' : '介质编号'
  const numberPlaceholder = hardDrive ? '如 YP2026041302-01' : archiveMedium === 'optical_disc'
    ? '如 GP2026073102-01' : '如 GP2026073102-01 或 YP2026041302-01'
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
    if (readOnly) { message.warning(`当前页面为只读，不能提交${mediumLabel}编号。`); return }
    if (mappingPlanRowRevision === null) { message.warning('归档计划版本尚未加载，请刷新后重试。'); return }
    const candidate = mappingDiscNumber.trim()
    if (!candidate) { message.warning(`请输入${numberLabel}。`); return }
    try {
      const result = await archive.mapping(
        caseId, expectedRevision, mappingPlanRowRevision, candidate,
      )
      setMappingPlanRowRevision(result.plan_row_revision)
      onFirstDiscNumberChange(candidate)
      message.success(hardDrive
        ? `已保存硬盘编号 ${candidate}。`
        : `已按序映射 ${result.parts.length} 个光盘编号。`)
      onCompleted()
    } catch { /* error already surfaced via useArchiveCompletion.error */ }
  }

  const runExport = () => {
    setNameDialogOpen(true)
  }

  const confirmExportName = async (wordFileName: string) => {
    setNameDialogOpen(false)
    try {
      // 目录授权只能使用一次，并会在导出时消耗；应始终重新选择目录，
      // 确保再次导出不会复用已消耗的令牌。
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
        message={hardDrive ? '待补硬盘编号' : archiveMedium === 'optical_disc' ? '待补盘号' : '待补介质编号'}
        description={hardDrive
          ? '压缩已完成且产物为一个超大单卷；编号可使用旧格式，也可在日期后加入两位用户标识。'
          : '压缩已完成；首盘号可使用旧格式，也可在日期后加入两位用户标识，系统将按 part 顺序生成全序列映射。'}
        action={<Space>
          <Input id={REVIEW_TARGET_IDS.discNumber} aria-label={numberLabel} placeholder={numberPlaceholder} value={mappingDiscNumber}
            disabled={readOnly} onChange={event => setMappingDiscNumber(event.target.value)} />
          <Button type="primary" loading={archive.busy} disabled={readOnly}
            onClick={() => { void submitMapping() }}>{hardDrive ? '提交硬盘编号' : '提交盘号映射'}</Button>
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
            ? '统一导出已完成，可再次导出获取最新 Word 与 RAR。'
            : hardDrive
              ? '完整 RAR、文件哈希与硬盘编号已对应完成，可开始导出。'
              : '全部 RAR、文件哈希与盘号已对应完成，可开始导出。'}
          action={<Space>
            <Input id={REVIEW_TARGET_IDS.discNumber} aria-label={numberLabel} placeholder={numberPlaceholder} value={mappingDiscNumber}
              disabled={readOnly} onChange={event => setMappingDiscNumber(event.target.value)} />
            <Button loading={archive.busy} disabled={readOnly}
              onClick={() => { void submitMapping() }}>{hardDrive ? '更新硬盘编号' : '更新盘号映射'}</Button>
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
      message={archiveMedium ? `${mediumLabel}编号` : '介质编号（可提前填写）'}
      description={status === 'compressing'
        ? hardDrive
          ? '压缩正在后台进行；完成后可填写硬盘编号。'
          : archiveMedium === 'optical_disc'
            ? '压缩正在后台进行；现在仍可填写新格式或旧格式首盘号，压缩完成后将沿用该编号。'
            : undefined
        : archiveMedium
          ? '可提前填写编号；系统会在压缩完成后按归档模式校验。'
          : '可提前填写新格式或旧格式的完整 GP/YP 编号；最终介质由压缩前归档总量决定。'}
      action={<Input id={REVIEW_TARGET_IDS.discNumber} aria-label={numberLabel} placeholder={numberPlaceholder} value={firstDiscNumber}
        disabled={readOnly} onChange={event => onFirstDiscNumberChange(event.target.value)} />}
    />
  )
}
