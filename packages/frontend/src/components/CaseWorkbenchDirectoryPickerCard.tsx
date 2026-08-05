// Layer 11: FE_Components — local Windows report-directory picker entry.
import React from 'react'
import { FolderOpenOutlined, PlusOutlined } from '@ant-design/icons'

interface Props {
  loading?: boolean
  onClick: () => void
}

export function CaseWorkbenchDirectoryPickerCard({ loading = false, onClick }: Props) {
  return (
    <button
      type="button"
      className="case-workbench-directory-picker"
      aria-label="上传报告目录"
      aria-busy={loading}
      disabled={loading}
      onClick={onClick}
    >
      <span className="case-workbench-directory-picker__plus" aria-hidden="true">
        <PlusOutlined />
      </span>
      <strong><FolderOpenOutlined /> 上传报告目录</strong>
      <span>{loading ? '正在打开本机选择器…' : '点击选择本机报告文件夹并立即解析'}</span>
    </button>
  )
}
