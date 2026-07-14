// Layer 11: FE_Components — 附件1 提取固定清单编辑器
// REQ-017: 表格列可编辑，行可增删。默认标准表头
import React from 'react'
import { Button, Table } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import type { TableData } from '@biji/shared/types'
import EditableField from './EditableField'

const DEFAULT_COLS: TableData['columns'] = [
  { key: 'no', title: '序号', width: '60' },
  { key: 'electronic_data', title: '电子数据', width: '220' },
  { key: 'source', title: '来源', width: '180' },
  { key: 'extraction_method', title: '提取方式', width: '180' },
  { key: 'md5_hash', title: '文件MD5哈希值', width: '260' },
]
const DEFAULT_ROWS = [
  { no: '1', electronic_data: '', source: '', extraction_method: '', md5_hash: '' },
]

interface Props {
  tableData: TableData
  onChange: (data: TableData) => void
}

export default function ExtractListEditor({ tableData, onChange }: Props) {
  const cols = tableData.columns.length > 0 ? tableData.columns : DEFAULT_COLS
  const rows = tableData.rows.length > 0 ? tableData.rows : DEFAULT_ROWS

  const addRow = () => {
    const newRow: Record<string, string> = {}
    cols.forEach(c => { newRow[c.key] = '' })
    onChange({ columns: [...cols], rows: [...rows, newRow] })
  }

  const updateCell = (rowIdx: number, colKey: string, value: string) => {
    const updated = rows.map((r, i) => i === rowIdx ? { ...r, [colKey]: value } : r)
    onChange({ columns: [...cols], rows: updated })
  }

  const removeRow = (rowIdx: number) => {
    onChange({ columns: [...cols], rows: rows.filter((_, i) => i !== rowIdx) })
  }

  return (
    <div>
      <Table
        dataSource={rows.map((r, i) => ({ ...r, _key: i }))}
        rowKey="_key"
        pagination={false} size="small" bordered
        columns={[
          ...cols.map(col => ({
            title: col.title, key: col.key, dataIndex: col.key,
            width: col.width ? parseInt(col.width) : 120,
            render: (_: unknown, record: Record<string, string | number>, rowIdx: number) => (
              <EditableField type="text" value={String(record[col.key] || '')}
                onChange={value => updateCell(rowIdx, col.key, value)} />
            ),
          })),
          {
            title: '', key: 'actions', width: 40,
            render: (_: unknown, __: unknown, rowIdx: number) => (
              <Button type="text" danger size="small" icon={<DeleteOutlined />}
                onClick={() => removeRow(rowIdx)} />
            ),
          },
        ]}
      />
      <Button type="dashed" icon={<PlusOutlined />} onClick={addRow} block style={{ marginTop: 8 }}>
        添加行
      </Button>
    </div>
  )
}
