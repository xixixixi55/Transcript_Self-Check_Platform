import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { InspectorLibraryRecord, InspectorSnapshot } from '@biji/shared/types'
import InspectorEditor from './InspectorEditor'

vi.mock('antd', () => ({
  Alert: ({ message }: { message: React.ReactNode }) => <div>{message}</div>,
  Button: ({ children, onClick, ...props }: { children?: React.ReactNode; onClick?: () => void; [key: string]: unknown }) => (
    <button {...props} onClick={onClick}>{children}</button>
  ),
  Card: ({ title, extra, children }: { title?: React.ReactNode; extra?: React.ReactNode; children: React.ReactNode }) => (
    <section><div>{title}{extra}</div>{children}</section>
  ),
  Modal: ({ open, children }: any) => open ? (
    <div role="dialog">
      {children}
    </div>
  ) : null,
  Space: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Tag: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
  Typography: { Text: ({ children }: { children: React.ReactNode }) => <span>{children}</span> },
}))

vi.mock('@ant-design/icons', () => ({
  DeleteOutlined: () => null,
  PlusOutlined: () => null,
}))

const activeInspector: InspectorLibraryRecord = {
  id: 'inspector-1', name: '张三', unit: '单位', police_number: '001', enabled: true,
  created_at: 'now', updated_at: 'now',
}

function snapshot(id: string, name: string, order: number): InspectorSnapshot {
  return { inspector_id: id, name, unit: `单位${name}`, police_number: `00${order + 1}`, selected_order: order }
}

describe('InspectorEditor', () => {
  it('通过末尾加号卡片添加检查人员', () => {
    const onChange = vi.fn()
    render(<InspectorEditor snapshots={[]} availableInspectors={[activeInspector]} onChange={onChange} />)

    fireEvent.click(screen.getByRole('button', { name: '添加检查人员' }))
    expect(screen.queryByRole('combobox')).toBeNull()
    fireEvent.click(screen.getByTestId(`inspector-option-${activeInspector.id}`))

    expect(onChange).toHaveBeenCalledWith([
      expect.objectContaining({ inspector_id: 'inspector-1', name: '张三', selected_order: 0 }),
    ])
  })

  it('空列表保留加号卡片，多人员使用网格容器并将加号放在末尾', () => {
    const empty = render(<InspectorEditor snapshots={[]} availableInspectors={[activeInspector]} onChange={vi.fn()} />)
    expect(empty.getByTestId('inspector-add-card')).toBeTruthy()
    empty.unmount()

    render(<InspectorEditor
      snapshots={[snapshot('one', '甲', 0), snapshot('two', '乙', 1), snapshot('three', '丙', 2), snapshot('four', '丁', 3)]}
      availableInspectors={[]}
      onChange={vi.fn()}
    />)

    expect(screen.getAllByTestId(/^inspector-card-/)).toHaveLength(4)
    expect(screen.getByTestId('inspector-add-card').className).toContain('inspector-selector__item--add')
    expect(screen.getByRole('list').className).toContain('inspector-selector__selected')
    expect(screen.getByRole('list').lastElementChild).toBe(screen.getByTestId('inspector-add-card'))
  })

  it('保留删除和拖拽排序，不显示上下调序入口', () => {
    const onChange = vi.fn()
    render(<InspectorEditor
      snapshots={[snapshot('one', '甲', 0), snapshot('two', '乙', 1)]}
      availableInspectors={[]}
      onChange={onChange}
    />)

    expect(screen.queryByRole('button', { name: /上移|下移/ })).toBeNull()
    fireEvent.dragStart(screen.getByTestId('inspector-card-0'))
    expect(screen.getByTestId('inspector-card-0').getAttribute('aria-grabbed')).toBe('true')
    fireEvent.drop(screen.getByTestId('inspector-card-1'))
    expect(onChange).toHaveBeenLastCalledWith([
      expect.objectContaining({ inspector_id: 'two', selected_order: 0 }),
      expect.objectContaining({ inspector_id: 'one', selected_order: 1 }),
    ])

    fireEvent.click(screen.getByRole('button', { name: '移除1' }))
    expect(onChange).toHaveBeenLastCalledWith([
      expect.objectContaining({ inspector_id: 'two', selected_order: 0 }),
    ])
  })

  it('停用人员保留在当前快照中，添加框只展示启用人员', () => {
    const onChange = vi.fn()
    render(<InspectorEditor
      snapshots={[{ inspector_id: 'disabled', name: '停用甲', unit: '单位甲', police_number: '001' }]}
      availableInspectors={[{ ...activeInspector, id: 'active', name: '启用乙', police_number: '002' }]}
      onChange={onChange}
    />)

    expect(screen.getByText('停用甲')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '添加检查人员' }))
    expect(screen.queryByTestId('inspector-option-disabled')).toBeNull()
    fireEvent.click(screen.getByTestId('inspector-option-active'))
    expect(onChange).toHaveBeenCalledWith([
      expect.objectContaining({ inspector_id: 'disabled' }),
      expect.objectContaining({ inspector_id: 'active', selected_order: 1 }),
    ])
  })

  it('展示检查人员字段和来源状态', () => {
    const onChange = vi.fn()
    render(<InspectorEditor
      snapshots={[
        { ...snapshot('one', '甲', 0), snapshot_id: 'snapshot-1' },
        { ...snapshot('two', '乙', 1), snapshot_id: 'snapshot-2' },
      ]}
      fieldStates={{
        'inspectors.snapshot-1.name': {
          field_path: 'inspectors.snapshot-1.name', source: 'user', confirmation: 'pending', revision: 1, last_changed_at: '2026-01-01T00:00:00Z',
        },
        'inspectors.snapshot-2.name': {
          field_path: 'inspectors.snapshot-2.name', source: 'system_default', confirmation: 'confirmed', revision: 0, last_changed_at: '2026-01-01T00:00:00Z',
        },
      }}
      availableInspectors={[]}
      onChange={onChange}
    />)

    expect(screen.getByText('甲')).toBeTruthy()
    expect(screen.getByText('单位：单位甲')).toBeTruthy()
    expect(screen.getByText('警号：001')).toBeTruthy()
    expect(screen.getByText('人工修改')).toBeTruthy()
    expect(screen.getByText('系统默认值')).toBeTruthy()
    expect(screen.getAllByText('待人工确认')).toHaveLength(1)
  })
})
