// 第 11 层：FE_Components — 检查人员库管理
import React, { useEffect, useMemo, useState } from 'react'
import { Alert, Button, Form, Input, Modal, Popconfirm, Space, Table, message } from 'antd'
import { DeleteOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'
import type { InspectorLibraryRecord } from '@biji/shared/types'

export function filterInspectorRecords(records: InspectorLibraryRecord[], search: string): InspectorLibraryRecord[] {
  const keyword = search.trim().toLowerCase()
  if (!keyword) return records
  return records.filter(record => [record.name, record.unit, record.position, record.police_number]
    .some(value => value.toLowerCase().includes(keyword)))
}

export default function InspectorManager() {
  const [records, setRecords] = useState<InspectorLibraryRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<InspectorLibraryRecord | null>(null)
  const [saving, setSaving] = useState(false)
  const [form] = Form.useForm()

  const fetchRecords = async () => {
    setLoading(true)
    try {
      const { data } = await axios.get(API_ENDPOINTS.INSPECTORS)
      setRecords(data.data || [])
      setError(null)
    } catch {
      setError('获取检查人员列表失败，请重试。')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchRecords() }, [])

  const filteredRecords = useMemo(() => {
    return filterInspectorRecords(records, search)
  }, [records, search])

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    setModalOpen(true)
  }

  const openEdit = (record: InspectorLibraryRecord) => {
    setEditing(record)
    form.setFieldsValue(record)
    setModalOpen(true)
  }

  const closeModal = () => {
    setModalOpen(false)
    setEditing(null)
    form.resetFields()
  }

  const handleSave = async () => {
    const values = await form.validateFields()
    setSaving(true)
    try {
      if (editing) {
        await axios.put(API_ENDPOINTS.INSPECTOR(editing.id), values)
        message.success('检查人员已更新')
      } else {
        await axios.post(API_ENDPOINTS.INSPECTORS, values)
        message.success('检查人员已添加')
      }
      closeModal()
      await fetchRecords()
    } catch {
      message.error('保存检查人员失败，请检查字段后重试。')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await axios.delete(API_ENDPOINTS.INSPECTOR(id))
      message.success('检查人员已删除')
      await fetchRecords()
    } catch {
      message.error('删除检查人员失败')
    }
  }

  const columns = [
    { title: '姓名', dataIndex: 'name', key: 'name' },
    { title: '单位', dataIndex: 'unit', key: 'unit' },
    { title: '职位', dataIndex: 'position', key: 'position', render: (value: string) => value || '待补充' },
    { title: '警号', dataIndex: 'police_number', key: 'police_number' },
    {
      title: '操作', key: 'actions', render: (_value: unknown, record: InspectorLibraryRecord) => (
        <Space>
          <Button type="link" icon={<EditOutlined />} onClick={() => openEdit(record)}>编辑</Button>
          <Popconfirm title="确定删除该检查人员？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <section className="management-surface inspector-manager" aria-labelledby="inspector-manager-title">
      <div className="management-surface__header">
        <div className="management-surface__header-copy">
          <h2 id="inspector-manager-title">人员列表</h2>
        </div>
        <Space className="inspector-manager__toolbar" wrap>
          <Input aria-label="搜索检查人员" placeholder="搜索姓名、单位、职位或警号" value={search} onChange={event => setSearch(event.target.value)} allowClear />
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新增检查人员</Button>
        </Space>
      </div>
      {error && <Alert className="management-surface__alert" type="error" showIcon message={error} action={<Button onClick={fetchRecords}>重试</Button>} />}
      <Table
        rowKey="id"
        columns={columns}
        dataSource={filteredRecords}
        loading={loading}
        locale={{ emptyText: error ? '暂无法加载数据' : search ? '没有匹配的检查人员' : '暂无检查人员' }}
      />
      <Modal title={editing ? '编辑检查人员' : '新增检查人员'} open={modalOpen} confirmLoading={saving} onOk={handleSave} onCancel={closeModal}>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="姓名" rules={[{ required: true, whitespace: true, message: '请输入姓名' }]}>
            <Input maxLength={100} />
          </Form.Item>
          <Form.Item name="unit" label="单位" rules={[{ required: true, whitespace: true, message: '请输入单位' }]}>
            <Input maxLength={200} />
          </Form.Item>
          <Form.Item name="position" label="职位" rules={[{ required: true, whitespace: true, message: '请输入职位' }]}>
            <Input maxLength={100} />
          </Form.Item>
          <Form.Item name="police_number" label="警号" rules={[{ required: true, whitespace: true, message: '请输入警号' }]}>
            <Input maxLength={64} />
          </Form.Item>
        </Form>
      </Modal>
    </section>
  )
}
