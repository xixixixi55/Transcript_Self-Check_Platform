// Layer 10: FE_Hooks — persistent template management actions.
import { useCallback, useEffect, useState } from 'react'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'
import type {
  TemplateManagementRecord,
  TemplateManagementResponse,
  DeriveTemplateRequest,
  RenameTemplateRequest,
  TemplateVersionRef,
} from '@biji/shared/types'

export type TemplateManagementErrorCode =
  | 'TEMPLATE_MANAGEMENT_LOAD_FAILED'
  | 'TEMPLATE_DEFAULT_SET_FAILED'
  | 'TEMPLATE_ADD_FAILED'
  | 'TEMPLATE_DELETE_FAILED'
  | 'TEMPLATE_DERIVE_FAILED'
  | 'TEMPLATE_RENAME_FAILED'
  | 'TEMPLATE_RULE_VALIDATION_FAILED'
  | 'TEMPLATE_UPLOAD_INVALID'
  | 'TEMPLATE_UPLOAD_TOO_LARGE'
  | 'DEFAULT_TEMPLATE_CANNOT_DELETE'
  | 'TEMPLATE_IN_USE'
  | 'TEMPLATE_VERSION_IMMUTABLE'
  | 'REVISION_CONFLICT'
  | 'TEMPLATE_CUSTOMIZATION_INVALID'
  | 'TEMPLATE_NAME_INVALID'

function requestErrorCode(error: unknown, fallback: TemplateManagementErrorCode): TemplateManagementErrorCode {
  const code = (error as any)?.response?.data?.detail?.code
  const known: TemplateManagementErrorCode[] = [
    'TEMPLATE_RULE_VALIDATION_FAILED', 'TEMPLATE_UPLOAD_INVALID', 'TEMPLATE_UPLOAD_TOO_LARGE',
    'DEFAULT_TEMPLATE_CANNOT_DELETE', 'TEMPLATE_IN_USE', 'TEMPLATE_VERSION_IMMUTABLE',
    'REVISION_CONFLICT',
    'TEMPLATE_CUSTOMIZATION_INVALID',
    'TEMPLATE_NAME_INVALID',
  ]
  return typeof code === 'string' && known.includes(code as TemplateManagementErrorCode)
    ? code as TemplateManagementErrorCode : fallback
}

function isManagementResponse(value: unknown): value is TemplateManagementResponse {
  if (!value || typeof value !== 'object') return false
  const response = value as Partial<TemplateManagementResponse>
  return Array.isArray(response.templates)
    && typeof response.defaults_revision === 'number'
    && (response.default_template_ref === null || typeof response.default_template_ref === 'object')
}

export function isTemplateManagementRecord(value: unknown): value is TemplateManagementRecord {
  if (!value || typeof value !== 'object') return false
  const record = value as Partial<TemplateManagementRecord>
  const customization = record.customization as Partial<TemplateManagementRecord['customization']> | undefined
  return record.schema_version === 1
    && typeof record.display_name === 'string'
    && typeof record.is_default === 'boolean'
    && typeof record.can_delete === 'boolean'
    && typeof record.can_customize === 'boolean'
    && customization !== undefined
    && typeof customization.document_title === 'string'
    && ['仿宋_GB2312', '仿宋', '宋体'].includes(customization.body_font || '')
    && [14, 15, 16, 17, 18].includes(customization.body_font_size || 0)
}

export function useTemplateManagement() {
  const [templates, setTemplates] = useState<TemplateManagementRecord[]>([])
  const [defaultTemplateRef, setDefaultTemplateRef] = useState<TemplateVersionRef | null>(null)
  const [defaultsRevision, setDefaultsRevision] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [errorCode, setErrorCode] = useState<TemplateManagementErrorCode | null>(null)

  const applyResponse = useCallback((value: unknown) => {
    if (!isManagementResponse(value)) throw new Error('invalid template management response')
    setTemplates(value.templates.filter(isTemplateManagementRecord))
    setDefaultTemplateRef(value.default_template_ref)
    setDefaultsRevision(value.defaults_revision)
  }, [])

  const reload = useCallback(async () => {
    setLoading(true)
    setErrorCode(null)
    try {
      const response = await axios.get<{ data: TemplateManagementResponse }>(
        API_ENDPOINTS.WORKBENCH_TEMPLATE_MANAGEMENT,
      )
      applyResponse(response.data.data)
    } catch (error) {
      setTemplates([])
      setErrorCode(requestErrorCode(error, 'TEMPLATE_MANAGEMENT_LOAD_FAILED'))
    } finally {
      setLoading(false)
    }
  }, [applyResponse])

  useEffect(() => { void reload() }, [reload])

  const setDefault = useCallback(async (templateRef: TemplateVersionRef) => {
    setSaving(true)
    setErrorCode(null)
    try {
      const response = await axios.put<{ data: TemplateManagementResponse }>(
        API_ENDPOINTS.WORKBENCH_TEMPLATE_DEFAULT,
        { template_ref: templateRef, expected_defaults_revision: defaultsRevision },
      )
      applyResponse(response.data.data)
      return true
    } catch (error) {
      setErrorCode(requestErrorCode(error, 'TEMPLATE_DEFAULT_SET_FAILED'))
      return false
    } finally {
      setSaving(false)
    }
  }, [applyResponse, defaultsRevision])

  const addTemplate = useCallback(async (input: {
    templateId: string
    version: string
    displayName: string
    file: File
  }) => {
    setSaving(true)
    setErrorCode(null)
    try {
      const form = new FormData()
      form.append('template_id', input.templateId)
      form.append('version', input.version)
      form.append('display_name', input.displayName)
      form.append('file', input.file)
      await axios.post(API_ENDPOINTS.WORKBENCH_TEMPLATES, form)
      await reload()
      return true
    } catch (error) {
      setErrorCode(requestErrorCode(error, 'TEMPLATE_ADD_FAILED'))
      return false
    } finally {
      setSaving(false)
    }
  }, [reload])

  const deleteTemplate = useCallback(async (templateRef: TemplateVersionRef) => {
    setSaving(true)
    setErrorCode(null)
    try {
      const response = await axios.delete<{ data: TemplateManagementResponse }>(
        API_ENDPOINTS.WORKBENCH_TEMPLATE(templateRef.template_id, templateRef.version),
      )
      applyResponse(response.data.data)
      return true
    } catch (error) {
      setErrorCode(requestErrorCode(error, 'TEMPLATE_DELETE_FAILED'))
      return false
    } finally {
      setSaving(false)
    }
  }, [applyResponse])

  const renameTemplate = useCallback(async (
    templateRef: TemplateVersionRef, displayName: string,
  ) => {
    setSaving(true)
    setErrorCode(null)
    try {
      const input: RenameTemplateRequest = { display_name: displayName }
      const response = await axios.put<{ data: TemplateManagementResponse }>(
        API_ENDPOINTS.WORKBENCH_TEMPLATE_DISPLAY_NAME(
          templateRef.template_id, templateRef.version,
        ),
        input,
      )
      applyResponse(response.data.data)
      return true
    } catch (error) {
      setErrorCode(requestErrorCode(error, 'TEMPLATE_RENAME_FAILED'))
      return false
    } finally {
      setSaving(false)
    }
  }, [applyResponse])

  const deriveTemplate = useCallback(async (input: DeriveTemplateRequest) => {
    setSaving(true)
    setErrorCode(null)
    try {
      await axios.post(API_ENDPOINTS.WORKBENCH_TEMPLATE_DERIVE, input)
      await reload()
      return true
    } catch (error) {
      setErrorCode(requestErrorCode(error, 'TEMPLATE_DERIVE_FAILED'))
      return false
    } finally {
      setSaving(false)
    }
  }, [reload])

  return {
    templates,
    defaultTemplateRef,
    defaultsRevision,
    loading,
    saving,
    errorCode,
    reload,
    setDefault,
    addTemplate,
    deleteTemplate,
    renameTemplate,
    deriveTemplate,
  }
}
