import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { InspectorLibraryRecord } from '@biji/shared/types'
import InspectorManager, { filterInspectorRecords } from './InspectorManager'

const mocks = vi.hoisted(() => ({
  axios: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
  form: {
    validateFields: vi.fn(async () => ({ name: '新增姓名', unit: '新增单位', police_number: '003' })),
    resetFields: vi.fn(),
    setFieldsValue: vi.fn(),
  },
}))

vi.mock('axios', () => ({ default: mocks.axios }))
vi.mock('@ant-design/icons', () => ({ DeleteOutlined: () => null, EditOutlined: () => null, PlusOutlined: () => null }))
vi.mock('antd', () => {
  const Form = ({ children }: { children: React.ReactNode }) => <form>{children}</form>
  Form.Item = ({ children, label }: { children: React.ReactNode; label: string }) => <label>{label}{children}</label>
  Form.useForm = () => [mocks.form]
  return {
    Alert: ({ message, action }: any) => <div>{message}{action}</div>,
    Button: ({ children, onClick, ...props }: any) => <button {...props} onClick={onClick}>{children}</button>,
    Form,
    Input: ({ value, onChange, 'aria-label': ariaLabel, placeholder }: any) => <input aria-label={ariaLabel} placeholder={placeholder} value={value || ''} onChange={onChange} />,
    Modal: ({ open, children, onOk }: any) => open ? <div role="dialog"><button onClick={onOk}>确定</button>{children}</div> : null,
    Popconfirm: ({ children }: any) => <>{children}</>,
    Space: ({ children }: any) => <div>{children}</div>,
    Switch: ({ checked, checkedChildren, unCheckedChildren, onChange }: any) => <button onClick={() => onChange(!checked)}>{checked ? checkedChildren : unCheckedChildren}</button>,
    Table: ({ columns, dataSource, locale }: any) => (
      <div>{dataSource.length === 0 ? locale.emptyText : dataSource.map((record: any) => (
        <div key={record.id}>{columns.map((column: any) => column.dataIndex
          ? <span key={column.key}>{record[column.dataIndex]}</span>
          : <span key={column.key}>{column.render?.(null, record)}</span>)}</div>
      ))}</div>
    ),
    message: { success: vi.fn(), error: vi.fn() },
  }
})

const record: InspectorLibraryRecord = {
  id: 'inspector-1', name: '合成姓名', unit: '合成单位', police_number: '001', enabled: true,
  created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
}

describe('InspectorManager', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.axios.get.mockResolvedValue({ data: { data: [record] } })
    mocks.axios.post.mockResolvedValue({ data: { data: record } })
    mocks.axios.put.mockResolvedValue({ data: { data: record } })
  })

  it('按姓名、单位或警号筛选人员', () => {
    expect(filterInspectorRecords([record], '合成单位')).toEqual([record])
    expect(filterInspectorRecords([record], '不存在')).toEqual([])
  })

  it('显示列表、搜索并支持启停', async () => {
    render(<InspectorManager />)
    expect(await screen.findByText('合成姓名')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('搜索检查人员'), { target: { value: '不存在' } })
    expect(screen.getByText('没有匹配的检查人员')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('搜索检查人员'), { target: { value: '' } })
    fireEvent.click(await screen.findByRole('button', { name: '启用' }))
    expect(mocks.axios.post).toHaveBeenCalledWith('/api/v1/inspectors/inspector-1/status', { enabled: false })
  })

  it('支持新增并刷新列表', async () => {
    render(<InspectorManager />)
    fireEvent.click(screen.getByRole('button', { name: '新增检查人员' }))
    fireEvent.click(screen.getByRole('button', { name: '确定' }))
    await waitFor(() => expect(mocks.axios.post).toHaveBeenCalledWith('/api/v1/inspectors', expect.any(Object)))
  })

  it('显示加载失败状态', async () => {
    mocks.axios.get.mockRejectedValueOnce(new Error('synthetic error'))
    render(<InspectorManager />)
    expect(await screen.findByText('获取检查人员列表失败，请重试。')).toBeTruthy()
  })
})
