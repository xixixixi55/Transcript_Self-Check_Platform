// 第 11 层：FE_Components — 对已验证模板进行白名单范围内的定制。
import { useEffect } from 'react'
import { Alert, Form, Input, InputNumber, Modal, Select, Typography } from 'antd'
import type {
  DeriveTemplateRequest, TemplateBodyFont, TemplateBodyFontSize, TemplateManagementRecord,
} from '@biji/shared/types'

interface TemplateCustomizationEditorProps {
  source: TemplateManagementRecord | null
  saving: boolean
  onCancel: () => void
  onSave: (input: DeriveTemplateRequest) => Promise<boolean>
}

interface EditorValues {
  templateId: string
  version: string
  displayName: string
  documentTitle: string
  bodyFont: TemplateBodyFont
  bodyFontSize: TemplateBodyFontSize
}

const bodyFonts: TemplateBodyFont[] = ['仿宋_GB2312', '仿宋', '宋体']
const bodyFontSizes: TemplateBodyFontSize[] = [14, 15, 16, 17, 18]

export function TemplateCustomizationEditor({
  source, saving, onCancel, onSave,
}: TemplateCustomizationEditorProps) {
  const [form] = Form.useForm<EditorValues>()
  const values = Form.useWatch([], form)
  const title = values?.documentTitle || '电子数据检查笔录'
  const font = values?.bodyFont || '仿宋_GB2312'
  const fontSize = values?.bodyFontSize || 16

  useEffect(() => {
    if (!source) return
    form.setFieldsValue({
      templateId: source.template_ref.template_id,
      version: '',
      displayName: `${source.display_name}（微调）`,
      documentTitle: source.customization.document_title,
      bodyFont: source.customization.body_font,
      bodyFontSize: source.customization.body_font_size,
    })
  }, [form, source])

  return <Modal
    title="前端微调模板"
    open={Boolean(source)}
    okText="发布新版本"
    cancelText="取消"
    confirmLoading={saving}
    destroyOnHidden
    width={760}
    onCancel={onCancel}
    onOk={() => form.submit()}
  >
    <Alert
      type="info"
      showIcon
      message="受控编辑"
      description="只修改固定标题和正文字体；附件表格、VML、图片区和分页保持不变。预览不代表 Word 最终分页。"
    />
    <Form
      form={form}
      layout="vertical"
      onFinish={async value => {
        if (!source) return
        const saved = await onSave({
          source_template_ref: source.template_ref,
          template_ref: { template_id: value.templateId.trim(), version: value.version.trim() },
          display_name: value.displayName.trim(),
          customization: {
            document_title: value.documentTitle.trim(),
            body_font: value.bodyFont,
            body_font_size: value.bodyFontSize,
          },
        })
        if (saved) onCancel()
      }}
    >
      <Form.Item name="templateId" label="新模板 ID" rules={[{ required: true, whitespace: true }]}>
        <Input />
      </Form.Item>
      <Form.Item name="version" label="新版本" rules={[{ required: true, whitespace: true }]}>
        <Input placeholder="例如 1.1.0" />
      </Form.Item>
      <Form.Item name="displayName" label="显示名称" rules={[{ required: true, whitespace: true }]}>
        <Input />
      </Form.Item>
      <Form.Item name="documentTitle" label="文书固定标题" rules={[{ required: true, whitespace: true, max: 40 }]}>
        <Input />
      </Form.Item>
      <Form.Item name="bodyFont" label="正文默认字体" rules={[{ required: true }]}>
        <Select options={bodyFonts.map(value => ({ value, label: value }))} />
      </Form.Item>
      <Form.Item name="bodyFontSize" label="正文字号（磅）" rules={[{ required: true }]}>
        <InputNumber min={14} max={18} step={1} />
      </Form.Item>
    </Form>
    <section aria-label="模板微调预览" style={{ border: '1px solid #d9d9d9', padding: 24, background: '#fff' }}>
      <Typography.Title level={3} style={{ textAlign: 'center', fontFamily: font }}>{title}</Typography.Title>
      <Typography.Paragraph style={{ fontFamily: font, fontSize }}>
        一、绪论<br />（一）委托单位：SYNTHETIC 预览单位<br />二、检查
      </Typography.Paragraph>
    </section>
  </Modal>
}
