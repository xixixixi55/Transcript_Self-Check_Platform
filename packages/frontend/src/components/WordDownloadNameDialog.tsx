// 第 11 层：FE_Components — 每次导出 Word 时询问下载文件名。
import React, { useEffect, useState } from 'react'
import { Input, Modal } from 'antd'
import { getDefaultWordDownloadName, toWordDownloadName, validateWordDownloadName } from '@biji/shared/utils'

interface WordDownloadNameDialogProps {
  open: boolean
  documentNumber?: string
  exporting?: boolean
  onCancel: () => void
  onConfirm: (downloadName: string) => void
}

export function WordDownloadNameDialog({
  open,
  documentNumber,
  exporting = false,
  onCancel,
  onConfirm,
}: WordDownloadNameDialogProps) {
  const [value, setValue] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    setValue(getDefaultWordDownloadName(documentNumber))
    setError(null)
  }, [documentNumber, open])

  const confirm = () => {
    const validationError = validateWordDownloadName(value)
    if (validationError) {
      setError(validationError)
      return
    }
    const result = toWordDownloadName(value)
    if (result) onConfirm(result.download_name)
  }

  return (
    <Modal
      open={open}
      title="Word 下载文件名"
      okText="开始导出"
      cancelText="取消"
      confirmLoading={exporting}
      destroyOnHidden
      onCancel={onCancel}
      onOk={confirm}
    >
      <p>此名称仅用于本次下载，不影响服务器生成的文件。</p>
      <Input
        aria-label="Word 下载文件名"
        value={value}
        status={error ? 'error' : undefined}
        onChange={event => { setValue(event.target.value); setError(null) }}
        onPressEnter={confirm}
        placeholder="请输入文件名"
      />
      {error && <div role="alert">{error}</div>}
    </Modal>
  )
}
