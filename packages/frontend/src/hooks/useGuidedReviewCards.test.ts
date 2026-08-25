import { act, renderHook } from '@testing-library/react'
import type { ArchiveTaskCardSummary, InspectionReport } from '@biji/shared/types'
import { describe, expect, it } from 'vitest'
import { getReviewPendingItems, REVIEW_TARGET_IDS } from './useReviewChecklist'
import type { GuidedReviewProjectionInput } from './useGuidedReviewCards'
import { deriveGuidedReviewProjection, useGuidedReviewCards } from './useGuidedReviewCards'

const syntheticReport: InspectionReport = {
  title: '电子数据检查笔录',
  document_number: 'SYN-TEST〔2026〕001号',
  case_number: 'SYNTHETIC-CASE-001',
  introduction: {
    entrust_unit: 'SYNTHETIC-UNIT',
    entrust_persons: ['SYNTHETIC-PERSON'],
    entrust_time: '2026年08月25日',
    case_summary: 'SYNTHETIC CASE SUMMARY',
    evidence_list: [{
      id: 'SYNTHETIC-EVIDENCE-1', device_type: '手机', evidence_number: 'SYNTHETIC-E-001',
      material_type: 'phone', material_type_status: 'confirmed_by_report', material_type_source: 'report',
      imei1: 'SYNTHETIC-IMEI', extractable: true,
    }],
    inspection_requirement: 'SYNTHETIC REQUIREMENT',
    inspection_time_range: '2026年08月25日09时00分至2026年08月25日10时00分',
    inspectors: [],
    inspector_snapshots: [{
      name: 'SYNTHETIC-INSPECTOR', unit: 'SYNTHETIC-UNIT', position: 'TEST', police_number: 'SYNTHETIC-BADGE',
    }],
    inspection_place: 'SYNTHETIC-PLACE',
  },
  inspection: {
    method: 'SYNTHETIC-METHOD', hardware_device: 'SYNTHETIC-HARDWARE', software_tools: [], process_steps: [],
    primary_software: {
      name: 'SYNTHETIC-SOFTWARE', version: '1.0', display_name: 'SYNTHETIC-SOFTWARE 1.0',
      confirmation_status: 'confirmed_by_report', provenance: [], candidates: [],
    },
    result: {
      evidence_number: 'SYNTHETIC-E-001', software_name: 'SYNTHETIC-SOFTWARE', software_version: '1.0',
      data_summary: 'SYNTHETIC DATA', rar_filename: '', md5_hash: '', file_size: '',
    },
  },
  attachments: { extract_list: { columns: [], rows: [] }, photo_ids: ['SYNTHETIC-PHOTO-1', 'SYNTHETIC-PHOTO-2'], disc_number: '' },
}

const archiveTask: ArchiveTaskCardSummary = {
  task_id: 'SYNTHETIC-TASK', case_id: 'SYNTHETIC-CASE-001', status: 'running',
  progress_kind: 'workflow_milestone', stage: 'winrar', stage_label: '正在生成压缩分卷',
  stage_index: 4, stage_count: 9, percent: 30, updated_at: '2026-08-25T01:00:00Z',
  last_heartbeat_at: null, output_bytes: 2048, output_volume_count: 1,
  last_output_change_at: null, worker_state: 'owned_running', started_at: '2026-08-25T00:59:00Z',
  finished_at: null, error_summary: null, allowed_actions: [],
}

function buildInput(report = syntheticReport): GuidedReviewProjectionInput {
  return {
    caseId: 'SYNTHETIC-CASE-001', report,
    pendingItems: getReviewPendingItems(report, undefined, null, {
      'introduction.evidence_list.completeness': {
        field_path: 'introduction.evidence_list.completeness', source: 'user', confirmation: 'confirmed',
        revision: 1, last_changed_at: '2026-08-25T01:00:00Z',
      },
    }),
    lifecycle: 'archiving' as const,
    archiveTask,
    archiveMedium: null,
    archiveParts: null,
    sourceStatus: 'available' as const,
    sourceRequiresReselection: false,
    leaseState: 'editable' as const,
    photoState: 'ready' as const,
  }
}

describe('guided review projection', () => {
  it('classifies existing facts without re-asking complete defaults or system-produced archive fields', () => {
    const projection = deriveGuidedReviewProjection(buildInput())

    expect(projection.pendingItems.some(item => item.targetId.includes('inspector'))).toBe(false)
    expect(projection.pendingItems.some(item => [
      REVIEW_TARGET_IDS.result('rar_filename'),
      REVIEW_TARGET_IDS.result('md5_hash'),
      REVIEW_TARGET_IDS.result('file_size'),
    ].includes(item.targetId))).toBe(false)
    expect(projection.systemStatus?.title).toBe('正在生成压缩分卷')
    expect(projection.history.map(item => `${item.title}${item.detail || ''}`).join(' ')).not.toMatch(
      /SYNTHETIC-TASK|revision|Worker|worker|令牌|token|[A-Z]:\\/,
    )
  })

  it('rebuilds refresh history from current facts and does not retain stale intermediate stages', () => {
    const running = deriveGuidedReviewProjection(buildInput())
    const completed = deriveGuidedReviewProjection({
      ...buildInput(), lifecycle: 'archive_verified',
      archiveTask: { ...archiveTask, status: 'succeeded', stage: 'completed', stage_label: '归档完成' },
      archiveMedium: 'optical_disc', archiveParts: [{ disc_number: 'GP20260825-01', size_bytes: 2048 }],
    })

    expect(running.history.some(item => item.id === 'archive-stage-winrar')).toBe(true)
    expect(completed.history.some(item => item.id === 'archive-stage-winrar')).toBe(false)
    expect(completed.history.some(item => item.title === '归档处理已完成')).toBe(true)
  })

  it('keeps the current action stable when a background fact adds a higher-priority item', () => {
    const initial = buildInput({ ...syntheticReport, document_number: '' })
    const { result, rerender } = renderHook(({ input }) => useGuidedReviewCards(input), {
      initialProps: { input: initial },
    })
    expect(result.current.currentAction?.pendingItem?.fieldLabel).toBe('文号')

    const sourceInvalid = {
      ...initial, sourceStatus: 'requires_reselection' as const, sourceRequiresReselection: true,
    }
    rerender({ input: sourceInvalid })
    expect(result.current.currentAction?.pendingItem?.fieldLabel).toBe('文号')
    expect(result.current.allActions.some(action => action.kind === 'source_recovery')).toBe(true)

    act(() => result.current.selectAction('source-recovery'))
    expect(result.current.currentAction?.kind).toBe('source_recovery')

    rerender({ input: buildInput() })
    expect(result.current.history.some(item => item.title === '文号已完成')).toBe(true)
  })
})
