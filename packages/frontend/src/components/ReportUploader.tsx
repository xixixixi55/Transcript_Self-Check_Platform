// Layer 11: FE_Components — 报告上传组件 (REQ-001)
import React, { useRef } from 'react'
import { Button, Space, Typography } from 'antd'
import { UploadOutlined, FolderOpenOutlined } from '@ant-design/icons'

const { Text } = Typography

interface Props {
  onUpload: (dirPath: string) => void
  loading?: boolean
}

export default function ReportUploader({ onUpload, loading }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)

  // Prompt 方式：手动输入路径（降级方案）
  const handlePromptPath = () => {
    const dirPath = prompt(
      '请输入报告目录路径\n（如 D:\\脱敏示例\\SYNTHETIC案件SYNTHETIC当事人被诈骗案_20260707161248_html）：'
    )
    if (dirPath) onUpload(dirPath.trim())
  }

  // webkitdirectory 方式：选择文件夹，提取路径传给后端
  const handleFolderSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (!files || files.length === 0) return
    // 获取第一个文件的完整路径，提取目录部分
    // webkitRelativePath: "report_dir/data/data_case_info.json"
    const relativePath = (files[0] as any).webkitRelativePath || ''
    // 从文件的完整路径反推目录（仅本地场景有效）
    // 降级：使用 prompt 方式，提示用户输入
    handlePromptPath()
  }

  return (
    <div style={{ textAlign: 'center', padding: 24 }}>
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {/* 方式一：选择文件夹 */}
        <input
          ref={inputRef}
          type="file"
          // @ts-ignore webkitdirectory is non-standard but supported by Chrome
          webkitdirectory=""
          directory=""
          style={{ display: 'none' }}
          onChange={handleFolderSelect}
        />
        <Button
          type="primary"
          size="large"
          icon={<FolderOpenOutlined />}
          onClick={() => inputRef.current?.click()}
          loading={loading}
          block
        >
          选择报告文件夹
        </Button>

        {/* 方式二：手动输入路径（降级兼容） */}
        <Button
          size="middle"
          icon={<UploadOutlined />}
          onClick={handlePromptPath}
          block
        >
          或手动输入目录路径
        </Button>

        <Text type="secondary" style={{ fontSize: 13 }}>
          支持美亚手机大师 FL-901V5 生成的 HTML 报告目录
          <br />
          需包含 data/ 目录及 data_case_info.json 等文件
        </Text>
      </Space>
    </div>
  )
}
