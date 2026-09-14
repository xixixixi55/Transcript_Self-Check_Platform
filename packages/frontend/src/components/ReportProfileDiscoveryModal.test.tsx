import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ReportProfileDiscoveryModal } from './ReportProfileDiscoveryModal'

describe('ReportProfileDiscoveryModal', () => {
  it('requires an explicit field choice and only submits the selected mapping', () => {
    const onConfirm = vi.fn()
    render(<ReportProfileDiscoveryModal
      discovery={{
        kind: 'discovery', discovery_token: 'discovery-synthetic',
        structure_fingerprint: 'synthetic-fingerprint', candidate_count: 2,
        limits: { max_depth: 4, max_files: 128, max_file_bytes: 1, max_total_bytes: 4 },
        candidates: [
          {
            candidate_id: 'candidate-case', canonical_field: 'case.case_name',
            source_file: 'metadata.json', json_path: '$/案件名称', collection_path: '$', value_type: 'string',
            confidence: 0.95, evidence: ['label:案件名称'], preview_values: ['SYNTHETIC-CASE'],
          },
          {
            candidate_id: 'candidate-model', canonical_field: 'material.model',
            source_file: 'metadata.json', json_path: '$/materials/*/设备型号', collection_path: '$/materials/*', value_type: 'string',
            confidence: 0.95, evidence: ['label:设备型号'], preview_values: ['SYNTHETIC-MODEL'],
          },
        ],
      }}
      onCancel={vi.fn()}
      onConfirm={onConfirm}
    />)
    const confirm = screen.getByRole('button', { name: '确认映射并创建案件' })
    expect(confirm.hasAttribute('disabled')).toBe(true)
    fireEvent.change(screen.getByPlaceholderText('例如：某厂商网页版报告 2026'), {
      target: { value: 'SYNTHETIC Profile' },
    })
    fireEvent.mouseDown(screen.getByRole('combobox', { name: '选择案件名称来源' }))
    fireEvent.click(screen.getByText('SYNTHETIC-CASE'))
    expect(screen.getByText('metadata.json · $/案件名称')).toBeTruthy()
    fireEvent.click(confirm)
    expect(onConfirm).toHaveBeenCalledWith(['candidate-case'], 'SYNTHETIC Profile')
  })
})
