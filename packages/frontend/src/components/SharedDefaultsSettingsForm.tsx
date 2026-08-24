// Layer 11: FE_Components — explicit editor for deployment-scoped record defaults.
import { useEffect, useState } from 'react'
import {
  Alert, Button, Form, Input, Modal, Radio, Skeleton,
} from 'antd'
import {
  ReloadOutlined, SaveOutlined,
} from '@ant-design/icons'
import type { InspectorLibraryRecord, InspectorSnapshot } from '@biji/shared/types'
import {
  sharedDefaultsToForm, useSharedDefaultsSettings,
} from '../hooks/useSharedDefaultsSettings'
import type { SharedDefaultsFormValues } from '../hooks/useSharedDefaultsSettings'
import { useRecordEditorCatalogs } from '../hooks/useRecordEditorCatalogs'
import { HardwareDeviceSelect } from './HardwareDeviceSelect'
import InspectorEditor from './InspectorEditor'

interface DefaultInspectorEditorProps {
  value?: InspectorSnapshot[]
  onChange?: (value: InspectorSnapshot[]) => void
  availableInspectors: InspectorLibraryRecord[]
  loading: boolean
  error: string | null
  disabled: boolean
}

function DefaultInspectorEditor({
  value = [], onChange, availableInspectors, loading, error, disabled,
}: DefaultInspectorEditorProps) {
  return (
    <InspectorEditor
      snapshots={value}
      availableInspectors={availableInspectors}
      loading={loading}
      error={error}
      disabled={disabled}
      onChange={onChange || (() => undefined)}
    />
  )
}

function validateInspectors(_: unknown, snapshots?: InspectorSnapshot[]) {
  const valid = (snapshots || []).every(snapshot => (
    snapshot.name.trim()
    && snapshot.unit.trim()
    && (snapshot.position || '').trim()
    && snapshot.police_number.trim()
    && ![snapshot.name, snapshot.unit, snapshot.position || '', snapshot.police_number]
      .some(value => value.includes('|'))
  ))
  return valid ? Promise.resolve() : Promise.reject(new Error('检查人员信息不完整或包含竖线字符，请删除后从人员库重新添加。'))
}

export function SharedDefaultsSettingsForm() {
  const { defaults, status, requestErrorCode, failedOperation, load, save } = useSharedDefaultsSettings()
  const catalogs = useRecordEditorCatalogs()
  const [form] = Form.useForm<SharedDefaultsFormValues>()
  const [dirty, setDirty] = useState(false)
  const documentNumberPrefix = Form.useWatch('documentNumberPrefix', form) || ''
  const documentNumberSuffix = Form.useWatch('documentNumberSuffix', form) || ''

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
            <h2 id="shared-defaults-basic-title">案件基础信息</h2>
          </div>
          <div className="shared-defaults-settings__grid">
            <Form.Item name="entrustUnitPrefix" label="委托单位前缀">
              <Input maxLength={200} placeholder="例如：宜都公安分局" allowClear />
            </Form.Item>
            <Form.Item className="shared-defaults-settings__wide" label="文号格式">
              <div className="shared-defaults-settings__document-number-format">
                <Form.Item name="documentNumberPrefix" noStyle>
                  <Input aria-label="文号编号前内容" maxLength={150}
                    placeholder="编号前内容，例如：SYN-TEST〔2026〕" allowClear />
                </Form.Item>
                <span className="shared-defaults-settings__document-number-slot">编号</span>
                <Form.Item name="documentNumberSuffix" noStyle>
                  <Input aria-label="文号编号后内容" maxLength={40}
                    placeholder="编号后内容，例如：号" allowClear />
                </Form.Item>
              </div>
              <div className="shared-defaults-settings__document-number-example" aria-live="polite">
                <span>示例</span>
                <strong>{documentNumberPrefix}142{documentNumberSuffix}</strong>
              </div>
            </Form.Item>
            <Form.Item name="inspectionPlace" label="检查地点">
              <Input maxLength={300} placeholder="输入默认检查地点" allowClear />
            </Form.Item>
            <Form.Item name="hardwareDevice" label="检查硬件设备">
              <HardwareDeviceSelect
                options={catalogs.deviceOptions}
                loading={catalogs.deviceLoading}
                disabled={Boolean(catalogs.deviceError)}
                placeholder="从电子设备管理中选择"
                allowClear
              />
            </Form.Item>
            {catalogs.deviceError && (
              <Alert className="shared-defaults-settings__catalog-error" type="error" showIcon
                message={catalogs.deviceError} />
            )}
            <Form.Item className="shared-defaults-settings__wide" name="inspectionMethod" label="检查方法">
              <Input.TextArea maxLength={2000} rows={4}
                placeholder="输入默认检查方法" allowClear showCount />
            </Form.Item>
            <Form.Item className="shared-defaults-settings__wide" name="dataSummary" label="数据摘要">
              <Input.TextArea maxLength={1000} rows={3}
                placeholder="输入默认数据摘要" allowClear showCount />
            </Form.Item>
            <Form.Item className="shared-defaults-settings__wide" name="inspectionRequirement" label="检查要求">
              <Input.TextArea maxLength={2000} rows={4}
                placeholder="输入默认检查要求" allowClear showCount />
            </Form.Item>
            <Form.Item name="hashAlgorithm" label="文件哈希算法">
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
            <h2 id="shared-defaults-inspectors-title">检查人员顺序</h2>
          </div>
          <Form.Item className="shared-defaults-settings__inspector-editor" name="inspectors"
            rules={[{ validator: validateInspectors }]}>
            <DefaultInspectorEditor
              availableInspectors={catalogs.inspectors}
              loading={catalogs.inspectorLoading}
              error={catalogs.inspectorError}
              disabled={status === 'loading' || status === 'saving'}
            />
          </Form.Item>
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
