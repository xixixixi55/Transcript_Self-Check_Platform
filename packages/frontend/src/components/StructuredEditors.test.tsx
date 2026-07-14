import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import EvidenceEditor from './EvidenceEditor'
import ExtractListEditor from './ExtractListEditor'
import InspectorEditor from './InspectorEditor'

vi.mock('antd', () => ({
  Button: ({ children, onClick }: { children: React.ReactNode; onClick?: () => void }) => (
    <button onClick={onClick}>{children}</button>
  ),
  Space: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Table: ({ columns, dataSource }: any) => (
    <div>{columns.map((column: any) => (
      <div key={column.key}>
        <span>{column.title}</span>
        {dataSource.map((record: any, index: number) => (
          <React.Fragment key={`${column.key}-${index}`}>
            {column.render?.(record[column.dataIndex], record, index)}
          </React.Fragment>
        ))}
      </div>
    ))}</div>
  ),
  Typography: { Text: ({ children }: { children: React.ReactNode }) => <span>{children}</span> },
}))

vi.mock('@ant-design/icons', () => ({ PlusOutlined: () => null, DeleteOutlined: () => null }))
vi.mock('./EditableField', () => ({
  default: ({ value, placeholder, onChange }: { value: string; placeholder?: string; onChange: (value: string) => void }) => (
    <button onClick={() => onChange('已修改')}>{value || placeholder || '点击编辑'}</button>
  ),
}))

describe('结构化编辑器', () => {
  it('检材字段通过 EditableField 回调更新数据', () => {
    const onChange = vi.fn()
    render(<EvidenceEditor items={[{ id: '1', device_type: 'iPhone', model: '', evidence_number: 'JC01' }]} onChange={onChange} />)

    fireEvent.click(screen.getByText('iPhone'))
    expect(onChange).toHaveBeenCalledWith(expect.arrayContaining([
      expect.objectContaining({ device_type: '已修改' }),
    ]))
  })

  it('检查人员字段通过 EditableField 回调更新数据', () => {
    const onChange = vi.fn()
    render(<InspectorEditor inspectors={[{ name: '张三', unit: '单位', badge_number: '001' }]} onChange={onChange} />)

    fireEvent.click(screen.getByText('张三'))
    expect(onChange).toHaveBeenCalledWith([
      { name: '已修改', unit: '单位', badge_number: '001' },
    ])
  })

  it('提取清单保留默认表头，并通过 EditableField 更新单元格', () => {
    const onChange = vi.fn()
    render(<ExtractListEditor tableData={{ columns: [], rows: [] }} onChange={onChange} />)

    expect(screen.getByText('电子数据')).toBeTruthy()
    fireEvent.click(screen.getAllByText('点击编辑')[0])
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({
      rows: [expect.objectContaining({ electronic_data: '已修改' })],
    }))
  })
})
