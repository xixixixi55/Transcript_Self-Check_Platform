import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import EvidenceEditor from './EvidenceEditor'
import ExtractListEditor from './ExtractListEditor'

vi.mock('antd', () => ({
  Alert: ({ message }: { message: React.ReactNode }) => <div>{message}</div>,
  Button: ({ children, onClick, ...props }: { children: React.ReactNode; onClick?: () => void; [key: string]: unknown }) => (
    <button {...props} onClick={onClick}>{children}</button>
  ),
  Card: ({ title, extra, children }: { title?: React.ReactNode; extra?: React.ReactNode; children: React.ReactNode }) => (
    <section><div>{title}{extra}</div>{children}</section>
  ),
  Space: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Select: ({ value, options, onChange, mode, 'aria-label': ariaLabel }: any) => (
    <select aria-label={ariaLabel} multiple={mode === 'multiple'} value={value} onChange={event => onChange(mode === 'multiple' ? [event.target.value] : event.target.value)}>
      {options.map((option: { label: string; value: string }) => (
        <option key={option.value} value={option.value}>{option.label}</option>
      ))}
    </select>
  ),
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
  Tag: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
  Typography: { Text: ({ children }: { children: React.ReactNode }) => <span>{children}</span> },
}))

vi.mock('@ant-design/icons', () => ({
  PlusOutlined: () => null,
  DeleteOutlined: () => null,
}))
vi.mock('./EditableField', () => ({
  default: ({ value, placeholder, onChange }: { value: string; placeholder?: string; onChange: (value: string) => void }) => (
    <button onClick={() => onChange(value === 'ABC123' ? 'def456' : '已修改')}>{value || placeholder || '点击编辑'}</button>
  ),
}))

describe('结构化编辑器', () => {
  it('检材字段通过 EditableField 回调更新数据', () => {
    const onChange = vi.fn()
    render(<EvidenceEditor items={[{ id: '1', device_type: 'iPhone', model: '', evidence_number: 'JC01' }]} onChange={onChange} />)

    fireEvent.click(screen.getByText('iPhone'))
    expect(onChange).toHaveBeenCalledWith(expect.arrayContaining([
      expect.objectContaining({ device_name: '已修改' }),
    ]))
  })

  it('检材类型选择写入用户确认状态', () => {
    const onChange = vi.fn()
    render(<EvidenceEditor items={[{
      id: '1', device_type: '合成设备', model: '', evidence_number: 'JC01',
      material_type: 'unconfirmed', material_type_status: 'unconfirmed',
    }]} onChange={onChange} />)

    fireEvent.change(screen.getByLabelText('检材1类型'), { target: { value: 'tablet' } })
    expect(onChange).toHaveBeenCalledWith([
      expect.objectContaining({
        material_type: 'tablet',
        material_type_status: 'confirmed_by_user',
        material_type_source: 'user',
      }),
    ])
  })

  it('检材卡片可拖拽排序并保留稳定 evidence_id', () => {
    const onChange = vi.fn()
    render(<EvidenceEditor items={[
      { id: 'legacy-1', evidence_id: 'evidence-1', device_type: '合成设备', model: '', evidence_number: 'SYN-01' },
      { id: 'legacy-2', evidence_id: 'evidence-2', device_type: '合成设备', model: '', evidence_number: 'SYN-02' },
    ]} onChange={onChange} />)

    fireEvent.dragStart(screen.getByTestId('evidence-card-0'))
    fireEvent.drop(screen.getByTestId('evidence-card-1'))

    expect(onChange).toHaveBeenCalledWith([
      expect.objectContaining({ evidence_id: 'evidence-2' }),
      expect.objectContaining({ evidence_id: 'evidence-1' }),
    ])
  })

  it('手机只显示 IMEI，平板只显示序列号但保留原始字段', () => {
    const phone = render(<EvidenceEditor items={[{
      id: 'phone', device_type: '手机', material_type: 'phone', imei1: '111111111111111',
      serial_number: 'PHONE-SERIAL', model: '', evidence_number: 'JC-PHONE',
    }]} onChange={vi.fn()} />)
    expect(screen.getByText('IMEI1：')).toBeTruthy()
    expect(screen.queryByText('序列号：')).toBeNull()
    phone.unmount()

    render(<EvidenceEditor items={[{
      id: 'tablet', device_type: '平板', material_type: 'tablet', imei1: '222222222222222',
      serial_number: 'TABLET-SERIAL', model: '', evidence_number: 'JC-TABLET',
    }]} onChange={vi.fn()} />)
    expect(screen.getByText('序列号：')).toBeTruthy()
    expect(screen.queryByText('IMEI1：')).toBeNull()
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

  it('提取方式为空时显示与 Word 一致的硬件语义兜底值', () => {
    const fallbackA = '使用SYNTHETIC-DEVICE-A对检材进行检查，将检出数据生成报告，然后对报告压缩并计算MD5值'
    const fallbackB = '使用SYNTHETIC-DEVICE-B对检材进行检查，将检出数据生成报告，然后对报告压缩并计算MD5值'
    const tableData = {
      columns: [],
      rows: [{ no: '1', electronic_data: 'SYNTHETIC.rar', source: '', extraction_method: '', md5_hash: '' }],
    }
    const { rerender } = render(<ExtractListEditor
      tableData={tableData}
      fallbackExtractionMethod={fallbackA}
      onChange={vi.fn()}
    />)

    expect(screen.getByText(fallbackA)).toBeTruthy()
    rerender(<ExtractListEditor
      tableData={tableData}
      fallbackExtractionMethod={fallbackB}
      onChange={vi.fn()}
    />)
    expect(screen.getByText(fallbackB)).toBeTruthy()
  })

  it('修改其他列时不会把提取方式展示兜底写回数据', () => {
    const onChange = vi.fn()
    render(<ExtractListEditor
      tableData={{
        columns: [],
        rows: [{ no: '1', electronic_data: 'SYNTHETIC.rar', source: '', extraction_method: '', md5_hash: '' }],
      }}
      fallbackExtractionMethod="使用SYNTHETIC-DEVICE对检材进行检查"
      onChange={onChange}
    />)

    fireEvent.click(screen.getByText('SYNTHETIC.rar'))
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({
      rows: [expect.objectContaining({
        electronic_data: '已修改',
        extraction_method: '',
      })],
    }))
  })

  it('提取清单中的 MD5 以大写显示并以大写写回', () => {
    const onChange = vi.fn()
    render(<ExtractListEditor
      tableData={{
        columns: [],
        rows: [{ no: '1', electronic_data: 'SYNTHETIC.rar', source: '', extraction_method: '', md5_hash: 'abc123' }],
      }}
      onChange={onChange}
    />)

    fireEvent.click(screen.getByText('ABC123'))
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({
      rows: [expect.objectContaining({ md5_hash: 'DEF456' })],
    }))
  })

  it('prefers brand and concrete model for the device name display', () => {
    render(<EvidenceEditor items={[{
      id: '1', device_type: '手机', device_name: '手机',
      brand: 'SYNTHETIC-BRAND', model: 'SYNTHETIC-MODEL', evidence_number: 'JC01',
    }]} onChange={vi.fn()} />)

    expect(screen.getByText('SYNTHETIC-BRAND SYNTHETIC-MODEL')).toBeTruthy()
  })
})
