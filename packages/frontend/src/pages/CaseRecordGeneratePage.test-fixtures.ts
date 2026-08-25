import type {
  ArchiveTaskCardSummary, ArchiveTaskResult, CaseDetail, CaseDraft, CaseShell,
  ClientIdentity, EditLease, InspectionReport, SharedDefaults, SourceRecord, TaskRecord,
} from '@biji/shared/types'

export const caseId = 'case-synthetic-archive-race'
export const identity: ClientIdentity = { client_instance_id: 'client-synthetic', session_id: 'session-synthetic', deployment_instance_id: 'synthetic-uat', observed_at: '2026-01-01T00:00:00Z', identity_kind: 'local_session' }
export const defaults: SharedDefaults = { schema_version: 1, deployment_instance_id: 'synthetic-uat', revision: 0, entrust_unit_prefix: '', document_number: '', inspection_place: '', inspection_method: '', hardware_device: '', inspector_order: [], disc_number_prefix: 'GP', migration_decision: 'ignored', updated_at: '2026-01-01T00:00:00Z' }
export const availableInspector = { id: 'inspector-synthetic', name: '张三', unit: 'SYNTHETIC-UNIT', position: 'SYNTHETIC-POSITION', police_number: 'SYN-001', created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' }
export const task: TaskRecord = { schema_version: 1, task_id: 'task-synthetic-parse', case_id: caseId, kind: 'parse', status: 'succeeded', stage: 'parse', percent: 100, counters: {}, input_revision: 0, attempt: 1, cancel_requested: false, revision: 0, created_at: '2026-01-01T00:00:00Z', finished_at: '2026-01-01T00:00:00Z' }
export const archiveTaskSummary: ArchiveTaskCardSummary = {
  progress_kind: 'workflow_milestone', stage: 'completed', stage_label: '归档完成', stage_index: 7,
  stage_count: 7, percent: 100, updated_at: '2026-01-01T00:00:00Z', last_heartbeat_at: null,
  output_bytes: 579, output_volume_count: 2, last_output_change_at: null, worker_state: 'released',
  task_id: 'archive-synthetic-1', case_id: caseId, status: 'succeeded', started_at: '2026-01-01T00:00:00Z',
  finished_at: '2026-01-01T00:00:10Z', error_summary: null, allowed_actions: ['view_result'],
}
export const completedArchiveResult: ArchiveTaskResult = {
  task_id: archiveTaskSummary.task_id, case_id: caseId, manifest_id: 'manifest-synthetic',
  archive_mode: 'standard_split', archive_medium: 'optical_disc', plan_row_revision: 4,
  verified_slots: [], assets: [],
  parts: [
    { part_id: 'part-1', filename: '合成案件.part1.rar', size_bytes: 123, md5: 'a'.repeat(32), disc_number: 'GP20260731-01', disc_date: '2026-07-31' },
    { part_id: 'part-2', filename: '合成案件.part2.rar', size_bytes: 456, md5: 'b'.repeat(32), disc_number: 'GP20260731-02', disc_date: '2026-07-31' },
  ],
  finished_at: archiveTaskSummary.finished_at,
}
export const lease: EditLease = { schema_version: 1, lease_id: 'lease-synthetic', case_id: caseId, session_id: identity.session_id, client_instance_id: identity.client_instance_id, lease_token: 'token-synthetic', last_heartbeat_at: '2026-01-01T00:00:00Z', expires_at: '2026-01-01T00:02:00Z', status: 'active', takeover_of_lease_id: null, revision: 0 }

export function report(discNumber = 'GP20260731-001'): InspectionReport {
  return {
    title: '电子数据检查笔录', document_number: 'SYN-TEST〔2026〕001号', case_number: 'SYN-CASE-001',
    introduction: { entrust_unit_prefix: 'SYNTHETIC-PREFIX', entrust_unit: 'SYNTHETIC-UNIT', entrust_persons: ['SYNTHETIC-PERSON'], entrust_time: '2026年7月31日', case_summary: 'SYNTHETIC/TEST', evidence_list: [], inspection_requirement: 'SYNTHETIC-REQUIREMENT', inspection_time_range: '2026年7月31日10点00分至2026年7月31日11点00分', inspectors: [], inspection_place: 'SYNTHETIC-PLACE' },
    inspection: { method: 'SYNTHETIC-METHOD', hardware_device: 'SYNTHETIC-DEVICE', software_tools: [], process_steps: [], result: { evidence_number: 'SYN-1', software_name: 'SYNTHETIC-TOOL', software_version: '1.0', data_summary: 'SYNTHETIC-DATA', rar_filename: '', md5_hash: '', file_size: '' } },
    attachments: { extract_list: { columns: [], rows: [] }, photo_ids: [], disc_number: discNumber },
  }
}

export function reportWithPhotos(value: InspectionReport, photoIds: string[]): InspectionReport {
  return { ...value, attachments: { ...value.attachments, photo_ids: photoIds, photo_groups: [] } }
}

export function detail(shellRevision: number, draftRevision: number, lifecycle: CaseShell['lifecycle'] = 'review_ready', discNumber = 'GP20260731-001', archiveSummary: ArchiveTaskCardSummary | null = null): CaseDetail {
  const draft: CaseDraft = { schema_version: 1, case_id: caseId, case_name: 'SYNTHETIC-CASE', case_summary: 'SYNTHETIC/TEST', case_number: 'SYN-CASE-001', report: report(discNumber), report_version: 'legacy-v1', field_states: {}, asset_refs: [], template_ref: null, archive_plan_id: null, lifecycle: lifecycle === 'archive_queued' ? 'review_ready' : lifecycle, revision: draftRevision, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' }
  const shell: CaseShell = { schema_version: 1, case_id: caseId, case_name: 'SYNTHETIC-CASE', case_summary: 'SYNTHETIC/TEST', case_number: 'SYN-CASE-001', source_id: 'source-synthetic', parse_task_id: task.task_id, lifecycle, report_available: true, revision: shellRevision, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z', archive_task_summary: archiveSummary }
  const source: SourceRecord = { schema_version: 1, source_id: 'source-synthetic', source_type: 'report_directory', case_id: caseId, allowed_root_id: 'root-synthetic', metadata: {}, fingerprint: 'fingerprint-synthetic', access_status: 'available', requires_reselection: false, revalidation_error_code: null, last_verified_at: '2026-01-01T00:00:00Z', revision: 0 }
  return { shell, draft, source, parse_task: task }
}
