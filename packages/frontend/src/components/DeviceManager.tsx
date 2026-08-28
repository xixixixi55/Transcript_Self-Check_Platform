// 第 11 层：FE_Components — 硬件设备管理组件
import React, { useState, useEffect } from 'react'
import { Table, Button, Modal, Form, Input, Space, Popconfirm, message } from 'antd'
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'
import type { HardwareDevice } from '@biji/shared/types'

export default function DeviceManager() {
  const [devices, setDevices] = useState<HardwareDevice[]>([])
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<HardwareDevice | null>(null)
  const [form] = Form.useForm()

  const fetchDevices = async () => {
    setLoading(true)
    try {
      const { data } = await axios.get(API_ENDPOINTS.DEVICES)
      setDevices(data.data || [])
    } catch {
      message.error('获取设备列表失败')
    }
    setLoading(false)
  }

  useEffect(() => { fetchDevices() }, [])

  const handleSave = async () => {
    let values
    try {
      values = await form.validateFields()
    } catch {
      return
    }
    try {
      if (editing) {
        await axios.put(API_ENDPOINTS.DEVICES + '/' + editing.id, values)
        message.success('已更新')
      } else {
        await axios.post(API_ENDPOINTS.DEVICES, values)
        message.success('已添加')
      }
      setModalOpen(false)
      setEditing(null)
      form.resetFields()
      fetchDevices()
    } catch {
      message.error('操作失败')
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await axios.delete(API_ENDPOINTS.DEVICES + '/' + id)
      message.success('已删除')
      fetchDevices()
    } catch {
      message.error('删除失败')
    }
  }

  const columns = [
    { title: '设备名称', dataIndex: 'name', key: 'name' },
    {
      title: '所属公司', dataIndex: 'company', key: 'company',
      render: (company: string) => company?.trim() || '待补充',
    },
    {
      title: '操作', key: 'action',
      render: (_: any, record: HardwareDevice) => (
        <Space>
          <Button type="link" icon={<EditOutlined />} onClick={() => {
            setEditing(record)
            form.setFieldsValue(record)
            setModalOpen(true)
          }}>编辑</Button>
          <Popconfirm title="确定删除?" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <section className="management-surface device-manager" aria-labelledby="device-manager-title">
      <div className="management-surface__header">
        <div className="management-surface__header-copy">
          <h2 id="device-manager-title">设备列表</h2>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => {
          setEditing(null)
          form.resetFields()
          setModalOpen(true)
        }}>添加设备</Button>
      </div>

      <Table columns={columns} dataSource={devices} rowKey="id" loading={loading} size="small" />

      <Modal title={editing ? '编辑设备' : '添加设备'} open={modalOpen} okText="保存" cancelText="取消"
        onOk={handleSave} onCancel={() => { setModalOpen(false); setEditing(null) }}>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="设备名称" rules={[{ required: true, message: '请输入设备名称' }]}>
            <Input placeholder="如 FL-901 手机取证塔" />
          </Form.Item>
          <Form.Item name="company" label="所属公司"
            rules={[{ required: true, whitespace: true, message: '请输入所属公司' }]}>
            <Input placeholder="如 美亚柏科" />
          </Form.Item>
        </Form>
      </Modal>
    </section>
  )
}
