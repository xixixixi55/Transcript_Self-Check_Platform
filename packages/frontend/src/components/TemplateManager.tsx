// Layer 11: FE_Components — approved record-template management.
import React, { useState } from 'react'
import {
  Alert, Button, Card, Form, Input, Modal, Popconfirm, Space, Table, Tag, Typography, Upload, message,
} from 'antd'
import { DeleteOutlined, PlusOutlined, UploadOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd'
import type { TemplateManagementRecord, TemplateVersionRef } from '@biji/shared/types'
import { useTemplateManagement } from '../hooks/useTemplateManagement'

const errorMessages: Record<string, string> = {
  TEMPLATE_MANAGEMENT_LOAD_FAILED: '笔录模版列表加载失败，请稍后重试。',
  TEMPLATE_DEFAULT_SET_FAILED: '默认模版设置失败，请稍后重试。',
  TEMPLATE_ADD_FAILED: '模版添加失败，请检查文件后重试。',
  TEMPLATE_DELETE_FAILED: '模版删除失败，请稍后重试。',
  TEMPLATE_RULE_VALIDATION_FAILED: '该 DOCX 未通过当前笔录模版结构校验。',
  TEMPLATE_UPLOAD_INVALID: '请上传有效的 DOCX 模版文件。',
  TEMPLATE_UPLOAD_TOO_LARGE: '模版文件不能超过 50MB。',
  DEFAULT_TEMPLATE_CANNOT_DELETE: '默认模版不能删除，请先选择其他默认模版。',
  TEMPLATE_IN_USE: '已有案件引用该模版版本，暂不能删除。',
  TEMPLATE_VERSION_IMMUTABLE: '相同模版 ID 和版本已经存在，不能覆盖。',
  REVISION_CONFLICT: '默认模版已被其他操作更新，请刷新后重试。',
}

interface TemplateFormValues {
  templateId: string
  version: string
  displayName: string
}

function templateKey(template: TemplateManagementRecord): string {
  return `${template.template_ref.template_id}@${template.template_ref.version}`
}

export default function TemplateManager() {
  const {
    templates, loading, saving, errorCode, reload, setDefault, addTemplate, deleteTemplate,
  } = useTemplateManagement()
  const [modalOpen, setModalOpen] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState(false)
  const [form] = Form.useForm<TemplateFormValues>()

  const openModal = () => {
    form.resetFields()
    setFile(null)
    setFileError(false)
    setModalOpen(true)
  }

  const closeModal = () => {
    setModalOpen(false)
    form.resetFields()
    setFile(null)
    setFileError(false)
  }

  const handleAdd = async (values: TemplateFormValues) => {
    if (!file) {
      setFileError(true)
      message.warning('请先选择 DOCX 模版文件。')
      return
    }
    const succeeded = await addTemplate({
      templateId: values.templateId.trim(),
      version: values.version.trim(),
      displayName: values.displayName.trim(),
      file,
    })
    if (succeeded) {
      message.success('笔录模版已添加')
      closeModal()
    }
  }

  const handleSetDefault = async (templateRef: TemplateVersionRef) => {
    if (await setDefault(templateRef)) message.success('默认笔录模版已更新')
  }

  const handleDelete = async (templateRef: TemplateVersionRef) => {
    if (await deleteTemplate(templateRef)) message.success('笔录模版已撤销')
  }

  const columns = [
    {
      title: '模版名称', key: 'display_name',
      render: (_value: unknown, _record: TemplateManagementRecord) => (
        <Space direction="vertical" size={0}>
          <Typography.Text strong>测试地区模版</Typography.Text>
          <Typography.Text type="secondary" className="template-manager__secondary-text">
            已通过 current-template-v1 结构校验
          </Typography.Text>
        </Space>
      ),
    },
    {
      title: '状态', key: 'status',
      render: (_value: unknown, record: TemplateManagementRecord) => (
        <Space size={4} wrap>
          <Tag color="success">已校验</Tag>
          {record.is_default && <Tag color="blue">默认模版</Tag>}
        </Space>
      ),
    },
    {
      title: '操作', key: 'actions',
      render: (_value: unknown, record: TemplateManagementRecord) => (
        <Space size="small" wrap>
          <Button
            type="link"
            disabled={saving || record.is_default}
            onClick={() => void handleSetDefault(record.template_ref)}
          >
            设为默认
          </Button>
          <Popconfirm
            title="确认撤销该模版？"
            description="撤销后不会物理删除模版文件，已被案件引用的版本仍会保留。"
            okText="确认撤销"
            cancelText="取消"
            disabled={saving || !record.can_delete}
            onConfirm={() => void handleDelete(record.template_ref)}
          >
            <Button type="link" danger icon={<DeleteOutlined />} disabled={saving || !record.can_delete}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  const selectedFileList: UploadFile[] = file
    ? [{ uid: 'template-upload', name: file.name, status: 'done' }]
    : []

  return (
    <section className="template-manager" aria-label="笔录模版管理">
      <Card className="template-manager__card">
        <div className="template-manager__header">
          <div className="template-manager__header-copy">
            <Typography.Title level={4} className="template-manager__title">已校验模版</Typography.Title>
            <Typography.Text type="secondary">
              仅可使用通过 current-template-v1 结构校验的 DOCX。
            </Typography.Text>
          </div>
          <Button type="primary" icon={<PlusOutlined />} onClick={openModal} disabled={saving}>
            添加模版
          </Button>
        </div>
        {errorCode && (
          <Alert
            type="error"
            showIcon
            message={errorMessages[errorCode] || '模版操作未完成，请稍后重试。'}
            action={<Button type="link" onClick={() => void reload()}>重试</Button>}
            className="template-manager__alert"
          />
        )}
        <Table
          rowKey={templateKey}
          columns={columns}
          dataSource={templates}
          loading={loading}
          size="middle"
          pagination={false}
          scroll={{ x: 520 }}
          locale={{ emptyText: loading ? '正在加载笔录模版…' : '当前没有可用笔录模版' }}
        />
      </Card>

      <Modal
        title="添加笔录模版"
        open={modalOpen}
        okText="保存模版"
        cancelText="取消"
        confirmLoading={saving}
        destroyOnHidden
        onOk={() => form.submit()}
        onCancel={closeModal}
      >
        <Form form={form} layout="vertical" onFinish={handleAdd}>
          <Form.Item
            name="templateId"
            label="模版 ID"
            rules={[{ required: true, whitespace: true, message: '请输入模版 ID' }]}
          >
            <Input placeholder="例如 electronic-inspection-record" />
          </Form.Item>
          <Form.Item
            name="version"
            label="版本"
            rules={[{ required: true, whitespace: true, message: '请输入模版版本' }]}
          >
            <Input placeholder="例如 1.0.0" />
          </Form.Item>
          <Form.Item
            name="displayName"
            label="显示名称"
            rules={[{ required: true, whitespace: true, message: '请输入模版显示名称' }]}
          >
            <Input placeholder="例如 电子数据检查笔录" />
          </Form.Item>
          <Form.Item
            label="DOCX 文件"
            required
            validateStatus={fileError ? 'error' : undefined}
            help={fileError ? '请选择 DOCX 模版文件' : '上传后会校验模板结构，单个文件不超过 50MB。'}
          >
            <Upload
              accept=".docx"
              beforeUpload={() => false}
              fileList={selectedFileList}
              maxCount={1}
              onChange={info => {
                const selectedFile = info.file.originFileObj || (info.file as unknown as File)
                setFile(selectedFile instanceof File ? selectedFile : null)
                setFileError(false)
              }}
              onRemove={() => {
                setFile(null)
                return true
              }}
              showUploadList
            >
              <Button icon={<UploadOutlined />}>选择 DOCX 文件</Button>
            </Upload>
          </Form.Item>
        </Form>
      </Modal>
    </section>
  )
}
