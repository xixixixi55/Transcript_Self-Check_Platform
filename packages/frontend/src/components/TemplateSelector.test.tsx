import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { TemplateVersion } from '@biji/shared/types'
import { TemplateSelector } from './TemplateSelector'

vi.mock('antd', () => ({
  Alert: ({ message, description }: { message: React.ReactNode; description?: React.ReactNode }) => (
    <div role="alert">{message}{description}</div>
  ),
  Button: ({ children, disabled, onClick }: { children: React.ReactNode; disabled?: boolean; onClick?: () => void }) => (
    <button disabled={disabled} onClick={onClick}>{children}</button>
  ),
  Card: ({ children, title }: { children: React.ReactNode; title: React.ReactNode }) => (
    <section><h2>{title}</h2>{children}</section>
  ),
  Spin: () => <span>loading</span>,
  Tag: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}))

const approved: TemplateVersion = {
  schema_version: 1,
  template_ref: { template_id: 'template-SYNTHETIC-approved', version: '1.0.0' },
  display_name: 'SYNTHETIC 已审核模板',
  fingerprint: 'sha256:SYNTHETIC-APPROVED',
  validation_rules: [{ rule_id: 'rule-SYNTHETIC', version: '1.0.0' }],
  approval_record: {
    approval_record_id: 'approval-SYNTHETIC-approved',
    status: 'approved',
    acceptance_summary: 'SYNTHETIC 验收摘要',
    recorded_at: '2026-07-30T00:00:00.000Z',
  },
  asset_id: 'asset-SYNTHETIC-approved',
  registered_at: '2026-07-30T00:00:00.000Z',
}

const pending: TemplateVersion = {
  ...approved,
  template_ref: { template_id: 'template-SYNTHETIC-pending', version: '2.0.0' },
  display_name: 'SYNTHETIC 未审核模板',
  approval_record: { ...approved.approval_record, status: 'pending' },
}

const props = {
  templates: [approved, pending],
  currentTemplateRef: null,
  loading: false,
  saving: false,
  disabled: false,
  errorCode: null,
  impact: null,
  onSelect: vi.fn(async () => true),
}

describe('TemplateSelector — delta scenario: 选择和切换模板', () => {
  it('shows only approved versions with ID, version, and acceptance summary', () => {
    render(<TemplateSelector {...props} />)

    expect(screen.getByRole('option', { name: /SYNTHETIC 已审核模板/ })).toBeTruthy()
    expect(screen.queryByRole('option', { name: /SYNTHETIC 未审核模板/ })).toBeNull()
    fireEvent.change(screen.getByLabelText('已审核模板版本'), {
      target: { value: JSON.stringify(['template-SYNTHETIC-approved', '1.0.0']) },
    })
    expect(screen.getByText('模板 ID：template-SYNTHETIC-approved')).toBeTruthy()
    expect(screen.getByText('版本：1.0.0')).toBeTruthy()
    expect(screen.getByText('验收摘要：SYNTHETIC 验收摘要')).toBeTruthy()
  })

  it('selects a version and explains Word invalidation without archive changes', () => {
    const onSelect = vi.fn(async () => true)
    const view = render(<TemplateSelector {...props} onSelect={onSelect} />)
    fireEvent.change(screen.getByLabelText('已审核模板版本'), {
      target: { value: JSON.stringify(['template-SYNTHETIC-approved', '1.0.0']) },
    })
    fireEvent.click(screen.getByRole('button', { name: '应用模板版本' }))
    expect(onSelect).toHaveBeenCalledWith(approved.template_ref)

    view.rerender(<TemplateSelector
      {...props}
      currentTemplateRef={approved.template_ref}
      impact={{
        word_artifact_validity: 'invalidated_by_template_change',
        archive_plan_changed: false,
        archive_task_created: false,
        manifest_changed: false,
        disc_mapping_changed: false,
      }}
    />)
    expect(screen.getByRole('alert').textContent).toContain('先前生成的 Word 已失效')
    expect(screen.getByRole('alert').textContent).toContain('RAR、Manifest、归档任务和光盘映射保持不变')
  })
})
