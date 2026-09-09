import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { GuidedReviewHistoryMaterial } from '../hooks/useGuidedReviewHistoryProjection'
import { GuidedReviewHistory } from './GuidedReviewHistory'

function material(id: string, imeiStatus: 'complete' | 'attention'): GuidedReviewHistoryMaterial {
  return {
    id,
    label: `检材 ${id}`,
    imeiStatus,
    targetId: `review-target-evidence-${id}`,
    photoCount: 0,
    requiredPhotoCount: 2,
    fields: [
      { label: 'IMEI 1', value: `${id}-IMEI-1` },
      { label: 'IMEI 2', value: imeiStatus === 'complete' ? `${id}-IMEI-2` : '待核对' },
      { label: '序列号', value: `${id}-SERIAL` },
    ],
  }
}

describe('GuidedReviewHistory IMEI grouping', () => {
  it('collapses complete IMEI materials together and shows attention materials separately', () => {
    render(<GuidedReviewHistory items={[{
      id: 'fact-evidence', tone: 'complete', title: '检材与图片 · 3 项',
      materials: [material('A', 'complete'), material('B', 'complete'), material('C', 'attention')],
    }]} />)

    const completeGroup = screen.getByText('检材信息完整（2项）').closest('details')
    expect(completeGroup).toBeTruthy()
    expect(completeGroup?.hasAttribute('open')).toBe(false)
    expect(screen.getByRole('listitem', { name: /检材 C/ })).toBeTruthy()
    expect(screen.getByText('C-SERIAL')).toBeTruthy()
  })

  it('edits material values directly in the Word preview and reports automatic saving', () => {
    const evidenceItems = [{
      id: 'SYNTHETIC-C', evidence_id: 'SYNTHETIC-C', device_type: 'SYNTHETIC Phone',
      device_name: 'SYNTHETIC Phone', evidence_number: 'SYN-JC-C', material_type: 'phone' as const,
      imei1: 'C-IMEI-1', imei2: '', serial_number: 'C-SERIAL', extractable: true,
    }]
    const onEvidenceItemsChange = vi.fn()
    const editableMaterial = {
      ...material('C', 'attention'),
      id: 'SYNTHETIC-C',
    }
    render(<GuidedReviewHistory items={[{
      id: 'fact-evidence', tone: 'complete', title: '检材与图片 · 1 项',
      materials: [editableMaterial],
    }]} evidenceItems={evidenceItems} onEvidenceItemsChange={onEvidenceItemsChange}
      saveState="saving" saveHasPending />)

    expect(screen.queryByRole('button', { name: '修改检材 C' })).toBeNull()
    expect(screen.queryByText('正在自动保存…')).toBeNull()
    expect(screen.getByText('设备：')).toBeTruthy()
    expect(screen.getByText('类型：')).toBeTruthy()
    expect(screen.getByText('提取情况：')).toBeTruthy()
    expect(screen.getByText('IMEI 1：')).toBeTruthy()
    expect(screen.getByText('IMEI 2：')).toBeTruthy()
    expect(screen.getByText('序列号：')).toBeTruthy()
    expect(screen.getByRole('button', { name: /SYN-JC-C，按 Enter 编辑/ })).toBeTruthy()
    expect(screen.getByRole('combobox', { name: '检材 C类型' })).toBeTruthy()
    expect(screen.getByRole('combobox', { name: '检材 C提取情况' })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /SYNTHETIC Phone，按 Enter 编辑/ }))
    const deviceInput = screen.getByDisplayValue('SYNTHETIC Phone')
    fireEvent.change(deviceInput, { target: { value: 'SYNTHETIC Updated Phone' } })
    fireEvent.blur(deviceInput)

    expect(onEvidenceItemsChange).toHaveBeenCalledWith([
      expect.objectContaining({ device_name: 'SYNTHETIC Updated Phone', brand: '', model: '' }),
    ])
    expect(screen.getByText('正在自动保存…')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /SYN-JC-C，按 Enter 编辑/ }))
    const numberInput = screen.getByDisplayValue('SYN-JC-C')
    fireEvent.change(numberInput, { target: { value: 'SYN-JC-C-UPDATED' } })
    fireEvent.blur(numberInput)
    expect(onEvidenceItemsChange).toHaveBeenCalledWith([
      expect.objectContaining({ evidence_number: 'SYN-JC-C-UPDATED' }),
    ])
  })
})
