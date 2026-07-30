import React from 'react'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import type { CaseDraft, TemplateVersion } from '@biji/shared/types'
import { TemplateSelector } from '../components/TemplateSelector'
import { useTemplateRegistry } from '../hooks/useTemplateRegistry'

vi.mock('axios', () => ({ default: { get: vi.fn(), put: vi.fn(), post: vi.fn() } }))
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
  template_ref: { template_id: 'template-SYNTHETIC-flow', version: '2.0.0' },
  display_name: 'SYNTHETIC 流程模板',
  fingerprint: 'sha256:SYNTHETIC-FLOW',
  validation_rules: [{ rule_id: 'rule-SYNTHETIC-flow', version: '1.0.0' }],
  approval_record: {
    approval_record_id: 'approval-SYNTHETIC-flow',
    status: 'approved',
    acceptance_summary: 'SYNTHETIC flow acceptance',
    recorded_at: '2026-07-30T00:00:00.000Z',
  },
  asset_id: 'asset-SYNTHETIC-flow',
  registered_at: '2026-07-30T00:00:00.000Z',
}

function FlowHarness() {
  const registry = useTemplateRegistry({
    caseId: 'case-SYNTHETIC-flow',
    currentTemplateRef: { template_id: approved.template_ref.template_id, version: '1.0.0' },
    expectedRevision: 11,
    enabled: true,
    editingEnabled: true,
    leaseId: 'lease-SYNTHETIC-flow',
    leaseToken: 'token-SYNTHETIC-flow',
  })
  return <TemplateSelector
    templates={registry.templates}
    currentTemplateRef={{ template_id: approved.template_ref.template_id, version: '1.0.0' }}
    loading={registry.loading}
    saving={registry.saving}
    disabled={false}
    errorCode={registry.errorCode}
    impact={registry.impact}
    onSelect={registry.selectTemplate}
  />
}

describe('T017 page flow — delta scenario: template switching does not archive', () => {
  it('loads, switches, and reports Word invalidation without archive requests', async () => {
    vi.mocked(axios.get).mockResolvedValue({ data: { data: [approved] } })
    vi.mocked(axios.put).mockResolvedValue({
      data: {
        data: {
          draft: {
            schema_version: 1,
            case_id: 'case-SYNTHETIC-flow',
            case_name: 'SYNTHETIC flow case',
            case_summary: 'TEST flow',
            report: {} as CaseDraft['report'],
            report_version: 'legacy-v1',
            field_states: {},
            asset_refs: [],
            template_ref: approved.template_ref,
            archive_plan_id: 'plan-SYNTHETIC-unchanged',
            lifecycle: 'review_ready',
            revision: 12,
            created_at: '2026-07-30T00:00:00.000Z',
            updated_at: '2026-07-30T00:01:00.000Z',
          },
          impact: {
            word_artifact_validity: 'invalidated_by_template_change',
            archive_plan_changed: false,
            archive_task_created: false,
            manifest_changed: false,
            disc_mapping_changed: false,
          },
        },
      },
    })
    render(<FlowHarness />)
    await waitFor(() => expect(screen.getByRole('option', { name: /SYNTHETIC 流程模板/ })).toBeTruthy())

    fireEvent.change(screen.getByLabelText('已审核模板版本'), {
      target: { value: JSON.stringify(['template-SYNTHETIC-flow', '2.0.0']) },
    })
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: '应用模板版本' }))
    })

    await waitFor(() => expect(screen.getByText(/先前生成的 Word 已失效/)).toBeTruthy())
    expect(vi.mocked(axios.put)).toHaveBeenCalledOnce()
    expect(vi.mocked(axios.post)).not.toHaveBeenCalled()
    expect(JSON.stringify(vi.mocked(axios.put).mock.calls)).not.toContain('archive')
    expect(JSON.stringify(vi.mocked(axios.put).mock.calls)).not.toContain('manifest')
    expect(JSON.stringify(vi.mocked(axios.put).mock.calls)).not.toContain('disc')
  })
})
