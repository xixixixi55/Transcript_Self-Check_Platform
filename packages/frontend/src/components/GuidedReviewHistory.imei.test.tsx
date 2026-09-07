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
    const onEditMaterial = vi.fn()
    render(<GuidedReviewHistory items={[{
      id: 'fact-evidence', tone: 'complete', title: '检材与图片 · 3 项',
      materials: [material('A', 'complete'), material('B', 'complete'), material('C', 'attention')],
    }]} onEditMaterial={onEditMaterial} />)

    const completeGroup = screen.getByText('IMEI 信息完整（2项）').closest('details')
    expect(completeGroup).toBeTruthy()
    expect(completeGroup?.hasAttribute('open')).toBe(false)
    expect(screen.getByRole('listitem', { name: /检材 C/ })).toBeTruthy()
    expect(screen.getByText('C-SERIAL')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: '修改检材 C' }))
    expect(onEditMaterial).toHaveBeenCalledWith('review-target-evidence-C')
  })
})
