// 第 10 层：FE_Hooks — 已批准模板的发现与案件选择。
import { useCallback, useEffect, useRef, useState } from 'react'
import axios from 'axios'
import {
  API_ENDPOINTS,
  TEMPLATE_APPROVAL_STATUS,
  TEMPLATE_CHANGE_WORD_ARTIFACT_VALIDITY,
  TEMPLATE_ERROR_CODES,
} from '@biji/shared/constants'
import type {
  CaseDraft,
  TemplateErrorCode,
  TemplateSelectionImpact,
  TemplateVersion,
  TemplateVersionRef,
} from '@biji/shared/types'

type TemplateRegistryErrorCode =
  | TemplateErrorCode
  | 'TEMPLATE_REGISTRY_LOAD_FAILED'
  | 'TEMPLATE_SELECTION_FAILED'
  | 'TEMPLATE_SELECTION_IMPACT_INVALID'
  | 'TEMPLATE_SELECTION_READ_ONLY'
  | 'REVISION_CONFLICT'
  | 'LEASE_CONFLICT'
  | 'LEASE_NOT_ACTIVE'
  | 'LEASE_EXPIRED'
  | 'LEASE_TAKEOVER_REQUIRED'

interface TemplateSelectionResponse {
  draft: CaseDraft
  impact: TemplateSelectionImpact
}

interface Options {
  caseId: string
  currentTemplateRef: TemplateVersionRef | null
  expectedRevision: number | null
  enabled: boolean
  editingEnabled: boolean
  leaseId?: string | null
  leaseToken?: string | null
  onSelected?: (draft: CaseDraft) => void | Promise<void>
}

const knownTemplateErrors = new Set<string>(Object.values(TEMPLATE_ERROR_CODES))
const knownSelectionErrors = new Set<TemplateRegistryErrorCode>([
  'REVISION_CONFLICT',
  'LEASE_CONFLICT',
  'LEASE_NOT_ACTIVE',
  'LEASE_EXPIRED',
  'LEASE_TAKEOVER_REQUIRED',
])

function nonEmpty(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

export function isApprovedTemplateVersion(value: unknown): value is TemplateVersion {
  if (!value || typeof value !== 'object') return false
  const template = value as Partial<TemplateVersion>
  return template.schema_version === 1
    && nonEmpty(template.template_ref?.template_id)
    && nonEmpty(template.template_ref?.version)
    && nonEmpty(template.display_name)
    && nonEmpty(template.fingerprint)
    && nonEmpty(template.asset_id)
    && nonEmpty(template.registered_at)
    && template.approval_record?.status === TEMPLATE_APPROVAL_STATUS.APPROVED
    && nonEmpty(template.approval_record.approval_record_id)
    && nonEmpty(template.approval_record.acceptance_summary)
    && nonEmpty(template.approval_record.recorded_at)
    && Array.isArray(template.validation_rules)
    && template.validation_rules.length > 0
    && template.validation_rules.every(rule => nonEmpty(rule?.rule_id) && nonEmpty(rule?.version))
}

function isSafeSelectionImpact(value: unknown): value is TemplateSelectionImpact {
  if (!value || typeof value !== 'object') return false
  const impact = value as Partial<TemplateSelectionImpact>
  return impact.word_artifact_validity === TEMPLATE_CHANGE_WORD_ARTIFACT_VALIDITY
    && impact.archive_plan_changed === false
    && impact.archive_task_created === false
    && impact.manifest_changed === false
    && impact.disc_mapping_changed === false
}

function requestErrorCode(error: unknown, fallback: TemplateRegistryErrorCode): TemplateRegistryErrorCode {
  const code = (error as any)?.response?.data?.detail?.code
  if (typeof code !== 'string') return fallback
  if (knownTemplateErrors.has(code)) return code as TemplateErrorCode
  return knownSelectionErrors.has(code as TemplateRegistryErrorCode)
    ? code as TemplateRegistryErrorCode : fallback
}

export function useTemplateRegistry(options: Options) {
  const {
    caseId, currentTemplateRef, expectedRevision, enabled, editingEnabled,
    leaseId, leaseToken, onSelected,
  } = options
  const requestSequence = useRef(0)
  const onSelectedRef = useRef(onSelected)
  const [templates, setTemplates] = useState<TemplateVersion[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [errorCode, setErrorCode] = useState<TemplateRegistryErrorCode | null>(null)
  const [impact, setImpact] = useState<TemplateSelectionImpact | null>(null)
  onSelectedRef.current = onSelected

  const reload = useCallback(async () => {
    const sequence = ++requestSequence.current
    if (!enabled || !caseId) {
      setTemplates([])
      setErrorCode(null)
      return
    }
    setLoading(true)
    setErrorCode(null)
    try {
      const response = await axios.get<{ data: TemplateVersion[] }>(API_ENDPOINTS.WORKBENCH_TEMPLATES)
      if (sequence !== requestSequence.current) return
      const values = Array.isArray(response.data.data) ? response.data.data : []
      setTemplates(values.filter(isApprovedTemplateVersion))
    } catch (error) {
      if (sequence === requestSequence.current) {
        setTemplates([])
        setErrorCode(requestErrorCode(error, 'TEMPLATE_REGISTRY_LOAD_FAILED'))
      }
    } finally {
      if (sequence === requestSequence.current) setLoading(false)
    }
  }, [caseId, enabled])

  useEffect(() => {
    setImpact(null)
    void reload()
    return () => { requestSequence.current += 1 }
  }, [reload])

  const selectTemplate = useCallback(async (templateRef: TemplateVersionRef) => {
    if (!editingEnabled || expectedRevision === null) {
      setErrorCode('TEMPLATE_SELECTION_READ_ONLY')
      return false
    }
    const selected = templates.find(template =>
      template.template_ref.template_id === templateRef.template_id
      && template.template_ref.version === templateRef.version)
    if (!selected) {
      setErrorCode(TEMPLATE_ERROR_CODES.NOT_APPROVED)
      return false
    }
    if (currentTemplateRef?.template_id === templateRef.template_id
      && currentTemplateRef.version === templateRef.version) return true

    setSaving(true)
    setErrorCode(null)
    try {
      const response = await axios.put<{ data: TemplateSelectionResponse }>(
        API_ENDPOINTS.WORKBENCH_CASE_TEMPLATE(caseId),
        {
          template_ref: templateRef,
          expected_revision: expectedRevision,
          lease_id: leaseId || null,
          lease_token: leaseToken || null,
        },
      )
      const result = response.data.data
      if (!isSafeSelectionImpact(result?.impact)) {
        setErrorCode('TEMPLATE_SELECTION_IMPACT_INVALID')
        return false
      }
      if (result.draft?.template_ref?.template_id !== templateRef.template_id
        || result.draft.template_ref.version !== templateRef.version) {
        setErrorCode('TEMPLATE_SELECTION_FAILED')
        return false
      }
      setImpact(result.impact)
      await onSelectedRef.current?.(result.draft)
      return true
    } catch (error) {
      setErrorCode(requestErrorCode(error, 'TEMPLATE_SELECTION_FAILED'))
      return false
    } finally {
      setSaving(false)
    }
  }, [
    caseId, currentTemplateRef?.template_id, currentTemplateRef?.version,
    editingEnabled, expectedRevision, leaseId, leaseToken, templates,
  ])

  return { templates, loading, saving, errorCode, impact, reload, selectTemplate }
}
