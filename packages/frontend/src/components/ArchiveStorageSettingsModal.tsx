import { useEffect, useState } from 'react'
import { Alert, Button, Modal, Skeleton, Space, Typography } from 'antd'
import { FolderOpenOutlined, RedoOutlined } from '@ant-design/icons'
import { useArchiveStorageSettings } from '../hooks/useArchiveStorageSettings'

const { Paragraph, Text, Title } = Typography

interface ArchiveStorageSettingsModalProps {
  open: boolean
  onClose: () => void
}

export function ArchiveStorageSettingsModal({ open, onClose }: ArchiveStorageSettingsModalProps) {
  const storage = useArchiveStorageSettings()
  const [resetConfirmOpen, setResetConfirmOpen] = useState(false)

  useEffect(() => {
    if (open) void storage.load().catch(() => undefined)
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  const configured = storage.settings?.configured_directory
  const active = storage.settings?.active_directory
  const resetToDefault = async () => {
    try {
      await storage.reset()
    } finally {
      setResetConfirmOpen(false)
    }
  }

  return (
    <Modal className="archive-storage-settings" title="归档存储设置" open={open}
      onCancel={onClose} footer={<Button onClick={onClose}>完成</Button>} destroyOnHidden>
      <Title level={5}>RAR 工作与存储目录</Title>
      <Paragraph type="secondary">
        压缩中的临时分卷和完成后的已验证 RAR 都保存在这里。案件数据、图片和日志仍保存在文枢数据目录。
      </Paragraph>
      {storage.error && <Alert type="error" showIcon message={storage.error}
        action={!storage.settings
          ? <Button size="small" onClick={() => void storage.load().catch(() => undefined)}>重试</Button>
          : undefined} />}
      {storage.settings && !storage.settings.valid && (
        <Alert type="warning" showIcon message="当前配置目录不可用"
          description="请重新选择一个现有且可写的本机目录，或恢复默认目录。" />
      )}
      {storage.loading && !storage.settings && (
        <div className="archive-storage-settings__loading" role="status" aria-live="polite"
          aria-label="正在读取归档目录设置">
          <Skeleton active title={false} paragraph={{ rows: 3 }} />
        </div>
      )}
      {storage.settings && <>
        <div className="archive-storage-settings__path-group">
          <Text type="secondary">当前生效目录</Text>
          <Text className="archive-storage-settings__path" copyable>{active}</Text>
        </div>
        <div className="archive-storage-settings__path-group">
          <Text type="secondary">{storage.settings.restart_required ? '重启后使用' : '当前配置'}</Text>
          <Text className="archive-storage-settings__path" copyable>{configured}</Text>
        </div>
      </>}
      {storage.settings?.restart_required && (
        <Alert type="info" showIcon message="设置已保存，重启文枢后生效"
          description="正在运行的归档不会迁移；重启前不能开始新的压缩任务。" />
      )}
      <Space wrap className="archive-storage-settings__actions">
        <Button type="primary" icon={<FolderOpenOutlined />} loading={storage.loading}
          onClick={() => void storage.selectDirectory().catch(() => undefined)}>
          选择目录
        </Button>
        <Button icon={<RedoOutlined />} disabled={!storage.settings?.custom || storage.loading}
          onClick={() => setResetConfirmOpen(true)}>
          恢复默认
        </Button>
      </Space>
      <Paragraph className="archive-storage-settings__hint" type="secondary">
        建议选择空间充足的非系统盘，并预留不少于待归档数据总量的可用空间。
      </Paragraph>
      <Modal title="恢复默认归档目录？" open={resetConfirmOpen}
        okText="恢复默认" cancelText="取消" confirmLoading={storage.loading}
        onCancel={() => setResetConfirmOpen(false)} onOk={() => void resetToDefault().catch(() => undefined)}>
        设置保存后需要重启文枢才会生效；已完成的归档文件不会被移动。
      </Modal>
    </Modal>
  )
}
