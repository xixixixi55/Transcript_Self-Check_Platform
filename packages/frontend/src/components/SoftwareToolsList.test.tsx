import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { PrimarySoftware, SoftwareItem } from '@biji/shared/types'
import SoftwareToolsList from './SoftwareToolsList'

vi.mock('antd', () => ({
  Button: ({ onClick, children }: { onClick?: () => void; children?: React.ReactNode }) => (
    <button type="button" onClick={onClick}>{children}</button>
  ),
  Space: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

vi.mock('@ant-design/icons', () => ({
  DeleteOutlined: () => null,
  PlusOutlined: () => null,
}))

vi.mock('./EditableField', () => ({
  default: ({ value, onChange, placeholder }: {
    value: string
    onChange: (value: string) => void
    placeholder?: string
  }) => (
    <button type="button" aria-label={placeholder} onClick={() => onChange(`${value}-EDIT`)}>
      {value || placeholder}
    </button>
  ),
}))

const primarySoftware: PrimarySoftware = {
  name: 'SYNTHETIC 主取证软件',
  version: 'V1.2.3',
  display_name: 'SYNTHETIC 主取证软件 V1.2.3',
  confirmation_status: 'confirmed_by_report',
  provenance: [],
  candidates: [],
}

describe('SoftwareToolsList', () => {
  it('把主取证软件合并为唯一可编辑行，并保留其他软件工具', () => {
    const onPrimarySoftwareChange = vi.fn()
    const tools: Array<SoftwareItem & { category?: string }> = [
      { category: 'main_forensic', name: primarySoftware.name, version: primarySoftware.version },
      { name: 'WinRAR压缩管理软件', version: '7.01' },
      { name: 'HashMyFiles', version: '2.51' },
    ]

    render(<SoftwareToolsList tools={tools} primarySoftware={primarySoftware}
      onPrimarySoftwareChange={onPrimarySoftwareChange} onChange={vi.fn()} readOnly />)

    expect(screen.getAllByText(primarySoftware.name)).toHaveLength(1)
    expect(screen.getAllByText(primarySoftware.version)).toHaveLength(1)
    expect(screen.getByText('报告自动识别')).toBeTruthy()
    expect(screen.getByText('WinRAR压缩管理软件')).toBeTruthy()
    expect(screen.getByText('HashMyFiles')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: '请输入主取证软件名称' }))
    expect(onPrimarySoftwareChange).toHaveBeenCalledWith('name', `${primarySoftware.name}-EDIT`)
  })

  it('主软件待确认时仍在同一行提供名称和版本入口', () => {
    const onPrimarySoftwareChange = vi.fn()
    const pending: PrimarySoftware = {
      ...primarySoftware,
      name: '',
      version: '',
      confirmation_status: 'unconfirmed',
      candidates: [
        { name: 'SYNTHETIC 候选甲', version: '1.0' },
        { name: 'SYNTHETIC 候选乙', version: '2.0' },
      ],
    }

    render(<SoftwareToolsList tools={[{ name: 'HashMyFiles', version: '2.51' }]}
      primarySoftware={pending} onPrimarySoftwareChange={onPrimarySoftwareChange}
      onChange={vi.fn()} readOnly />)

    expect(screen.getByText('待确认')).toBeTruthy()
    expect(screen.getByText('报告候选存在冲突，请确认名称和版本后再导出。')).toBeTruthy()
    expect(screen.getByRole('button', { name: '请输入主取证软件名称' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '请输入主取证软件版本' })).toBeTruthy()
  })
})
