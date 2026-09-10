import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useState } from 'react'
import type { EvidenceItem } from '@biji/shared/types'
import type { GuidedReviewHistoryMaterial } from '../hooks/useGuidedReviewHistoryProjection'
import { buildReportHistory } from '../hooks/useGuidedReviewHistoryProjection'
import { syntheticReport } from '../hooks/useGuidedReviewCards.testFixtures'
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

function EditableGroupingHarness() {
  const [evidenceItems, setEvidenceItems] = useState<EvidenceItem[]>([{
    ...syntheticReport.introduction.evidence_list[0],
    id: 'SYNTHETIC-ATTENTION', evidence_id: 'SYNTHETIC-ATTENTION',
    device_name: '', device_type: '', brand: '', model: '', material_type: 'phone' as const,
    imei1: '111111111111111', imei2: '',
  }])
  const report = {
    ...syntheticReport,
    introduction: { ...syntheticReport.introduction, evidence_list: evidenceItems },
  }
  return <GuidedReviewHistory items={buildReportHistory(report)} evidenceItems={evidenceItems}
    onEvidenceItemsChange={setEvidenceItems} saveState="saving" saveHasPending />
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
      holder_name: 'SYNTHETIC-HOLDER-A', imei1: '', imei2: '', serial_number: 'C-SERIAL',
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
    expect(screen.getByText('持有人：')).toBeTruthy()
    expect(screen.getByText('类型：')).toBeTruthy()
    expect(screen.getByText('提取情况：')).toBeTruthy()
    expect(screen.getByText('IMEI 1：')).toBeTruthy()
    expect(screen.getByText('IMEI 2：')).toBeTruthy()
    expect(screen.getByText('序列号：')).toBeTruthy()
    expect(screen.getByRole('button', { name: /SYN-JC-C，按 Enter 编辑/ })).toBeTruthy()
    expect(screen.getByRole('combobox', { name: '检材 C类型' })).toBeTruthy()
    expect(screen.getByText('可提取')).toBeTruthy()

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

    fireEvent.click(screen.getByRole('button', { name: /SYNTHETIC-HOLDER-A，按 Enter 编辑/ }))
    const holderInput = screen.getByDisplayValue('SYNTHETIC-HOLDER-A')
    fireEvent.change(holderInput, { target: { value: 'SYNTHETIC-HOLDER-B' } })
    fireEvent.blur(holderInput)
    expect(onEvidenceItemsChange).toHaveBeenCalledWith([
      expect.objectContaining({ holder_name: 'SYNTHETIC-HOLDER-B' }),
    ], { affectsCompleteness: false })
  })

  it('moves an attention material into the complete group as soon as its missing information is filled', () => {
    render(<EditableGroupingHarness />)

    expect(screen.queryByText('检材信息完整（1项）')).toBeNull()
    expect(screen.getByText('检材信息待核对')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: '待填写，按 Enter 编辑' }))
    const deviceInput = screen.getByRole('textbox')
    fireEvent.change(deviceInput, { target: { value: 'SYNTHETIC Phone' } })
    fireEvent.blur(deviceInput)

    expect(screen.queryByText('检材信息完整（1项）')).toBeNull()
    expect(screen.getByText('检材信息待核对')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: '待核对，按 Enter 编辑' }))
    const imeiInput = screen.getByRole('textbox')
    fireEvent.change(imeiInput, { target: { value: '222222222222222' } })
    fireEvent.blur(imeiInput)

    expect(screen.getByText('检材信息完整（1项）')).toBeTruthy()
    expect(screen.queryByText('检材信息待核对')).toBeNull()
  })
})
