// Layer 11: FE_Components — explicit editor for deployment-scoped record defaults.
import { useEffect, useState } from 'react'
import {
  Alert, Button, Form, Input, Modal, Radio, Skeleton, Space, Typography,
} from 'antd'
import {
  ArrowDownOutlined, ArrowUpOutlined, DeleteOutlined, PlusOutlined,
  ReloadOutlined, SaveOutlined,
} from '@ant-design/icons'
import {
  sharedDefaultsToForm, useSharedDefaultsSettings,
} from '../hooks/useSharedDefaultsSettings'
import type { SharedDefaultsFormValues } from '../hooks/useSharedDefaultsSettings'

const { Paragraph, Text } = Typography
const noSeparatorRule = { pattern: /^[^|]*$/, message: '不能包含竖线字符“|”' }

export function SharedDefaultsSettingsForm() {
  const { defaults, status, requestErrorCode, failedOperation, load, save } = useSharedDefaultsSettings()
  const [form] = Form.useForm<SharedDefaultsFormValues>()
  const [dirty, setDirty] = useState(false)

  useEffect(() => {
    if (!defaults) return
    form.setFieldsValue(sharedDefaultsToForm(defaults))
    setDirty(false)
  }, [defaults, form])

  const handleSave = async () => {
    const values = await form.validateFields()
    const saved = await save(values)
    if (saved) {
      form.setFieldsValue(sharedDefaultsToForm(saved))
      setDirty(false)
    }
  }

  const handleReload = () => {
    if (!dirty) {
      void load()
      return
    }
    Modal.confirm({
      title: '放弃未保存的修改？',
      content: '重新加载会用服务端当前值替换本页尚未保存的修改。',
      okText: '放弃并重新加载',
      cancelText: '继续编辑',
      onOk: () => load(),
    })
  }

  if (status === 'loading' && !defaults) {
    return <Skeleton active paragraph={{ rows: 10 }} title={{ width: '38%' }} />
  }

  if (!defaults) {
    return (
      <Alert type="error" showIcon message="无法加载笔录默认设置"
        description="当前默认值没有显示，尚未对任何设置进行修改。"
        action={<Button icon={<ReloadOutlined />} disabled={status === 'loading'}
          onClick={handleReload}>重新加载</Button>} />
    )
  }

  return (
    <div className="shared-defaults-settings">
      {status === 'conflict' && (
        <Alert className="shared-defaults-settings__status" type="warning" showIcon
          message="设置已被其他窗口更新"
          description="为避免覆盖较新的内容，请放弃本页修改并重新加载后再编辑。"
          action={<Button icon={<ReloadOutlined />}
            onClick={handleReload}>放弃修改并重新加载</Button>} />
      )}
      {status === 'failed' && requestErrorCode && (
        <Alert className="shared-defaults-settings__status" type="error" showIcon
          message={failedOperation === 'load' ? '重新加载默认设置失败' : '默认设置未保存'}
          description={failedOperation === 'load'
            ? `当前页面内容和未保存修改仍保留，请检查连接后重试（错误代码：${requestErrorCode}）。`
            : `服务端原有设置保持不变，请检查连接或输入内容后重试（错误代码：${requestErrorCode}）。`} />
      )}
      {status === 'saved' && (
        <Alert className="shared-defaults-settings__status" type="success" showIcon
          message="笔录默认设置已保存" />
      )}

      <Form form={form} layout="vertical" requiredMark={false}
        disabled={status === 'loading' || status === 'saving'}
        onValuesChange={() => setDirty(true)} onFinish={() => void handleSave()}>
        <section className="shared-defaults-settings__section" aria-labelledby="shared-defaults-basic-title">
          <div className="shared-defaults-settings__section-heading">
            <div>
              <h2 id="shared-defaults-basic-title">案件基础信息</h2>
              <Paragraph>报告没有识别出真实内容时，系统才会使用这些值预填新案件。</Paragraph>
            </div>
            <Text type="secondary">当前版本 {defaults.revision}</Text>
          </div>
          <div className="shared-defaults-settings__grid">
            <Form.Item name="entrustUnitPrefix" label="委托单位前缀">
              <Input maxLength={200} placeholder="例如：宜都公安分局" allowClear />
            </Form.Item>
            <Form.Item name="documentNumber" label="文号">
              <Input maxLength={200} placeholder="输入完整文号，不会自动递增" allowClear />
            </Form.Item>
            <Form.Item name="inspectionPlace" label="检查地点">
              <Input maxLength={300} placeholder="输入默认检查地点" allowClear />
            </Form.Item>
            <Form.Item name="hardwareDevice" label="检查硬件设备">
              <Input maxLength={300} placeholder="输入默认取证硬件设备" allowClear />
            </Form.Item>
            <Form.Item className="shared-defaults-settings__wide" name="inspectionMethod" label="检查方法">
              <Input.TextArea maxLength={2000} rows={4}
                placeholder="输入默认检查方法" allowClear showCount />
            </Form.Item>
            <Form.Item name="discNumberPrefix" label="光盘编号前缀"
              extra="这里只保存前缀，不会复制日期、序号或完整光盘编号。">
              <Input maxLength={20} placeholder="例如：GP" allowClear />
            </Form.Item>
            <Form.Item name="hashAlgorithm" label="文件哈希算法"
              extra="新建案件会固化所选算法；历史案件仍按 MD5 显示和校验。">
              <Radio.Group className="shared-defaults-settings__hash-options"
                optionType="button" buttonStyle="solid"
                options={[
                  { label: 'MD5', value: 'md5' },
                  { label: 'SHA-1', value: 'sha1' },
                  { label: 'SHA-256', value: 'sha256' },
                ]} />
            </Form.Item>
          </div>
        </section>

        <section className="shared-defaults-settings__section" aria-labelledby="shared-defaults-inspectors-title">
          <div className="shared-defaults-settings__section-heading">
            <div>
              <h2 id="shared-defaults-inspectors-title">检查人员顺序</h2>
              <Paragraph>按实际落入笔录的顺序排列；清空全部人员表示不设置默认检查人员。</Paragraph>
            </div>
          </div>
          <Form.List name="inspectors">
            {(fields, { add, remove, move }) => (
              <div className="shared-defaults-settings__inspectors">
                {fields.length === 0 && (
                  <div className="shared-defaults-settings__empty">暂未设置默认检查人员</div>
                )}
                {fields.map((field, index) => (
                  <div className="shared-defaults-settings__inspector" key={field.key}>
                    <span className="shared-defaults-settings__order">{index + 1}</span>
                    <Form.Item name={[field.name, 'name']} label="姓名"
                      rules={[{ required: true, whitespace: true, message: '请输入姓名' }, noSeparatorRule]}>
                      <Input maxLength={100} />
                    </Form.Item>
                    <Form.Item name={[field.name, 'unit']} label="单位"
                      rules={[{ required: true, whitespace: true, message: '请输入单位' }, noSeparatorRule]}>
                      <Input maxLength={200} />
                    </Form.Item>
                    <Form.Item name={[field.name, 'position']} label="职位"
                      rules={[{ required: true, whitespace: true, message: '请输入职位' }, noSeparatorRule]}>
                      <Input maxLength={100} />
                    </Form.Item>
                    <Form.Item name={[field.name, 'badgeNumber']} label="警号"
                      rules={[{ required: true, whitespace: true, message: '请输入警号' }, noSeparatorRule]}>
                      <Input maxLength={64} />
                    </Form.Item>
                    <Space className="shared-defaults-settings__row-actions" size={4}>
                      <Button aria-label={`上移第${index + 1}名检查人员`} icon={<ArrowUpOutlined />}
                        disabled={index === 0} onClick={() => move(index, index - 1)} />
                      <Button aria-label={`下移第${index + 1}名检查人员`} icon={<ArrowDownOutlined />}
                        disabled={index === fields.length - 1} onClick={() => move(index, index + 1)} />
                      <Button danger aria-label={`删除第${index + 1}名检查人员`} icon={<DeleteOutlined />}
                        onClick={() => remove(field.name)} />
                    </Space>
                  </div>
                ))}
                <Button type="dashed" icon={<PlusOutlined />}
                  onClick={() => add({ name: '', unit: '', position: '', badgeNumber: '' })}>添加检查人员</Button>
              </div>
            )}
          </Form.List>
        </section>

        <div className="shared-defaults-settings__actions">
          <Button icon={<ReloadOutlined />} disabled={status === 'saving' || status === 'loading'}
            onClick={handleReload}>
            {dirty ? '放弃修改并重新加载' : '重新加载'}
          </Button>
          <Button type="primary" htmlType="submit" icon={<SaveOutlined />}
            loading={status === 'saving'} disabled={!dirty || status === 'loading'}>
            保存默认设置
          </Button>
        </div>
      </Form>
    </div>
  )
}
