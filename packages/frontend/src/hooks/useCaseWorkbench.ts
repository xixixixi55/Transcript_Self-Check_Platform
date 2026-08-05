// Layer 10: FE_Hooks — persistent case list/detail requests with stale-response guards.
import { useCallback, useEffect, useRef, useState } from 'react'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'
import type {
  ArchiveTaskHistory, ArchiveTaskPublicDetail, ArchiveTaskResult,
  CaseDeletionResult, CaseDetail, CaseListPage, CaseShell, CaseSubmission,
  CaseSubmissionRequest, TaskRecord,
} from '@biji/shared/types'
import { getSourceAuthorizationEnabled } from './useSourceAuthorizationPreference'

export const CASE_PAGE_SIZE = 6

export interface WorkbenchError {
  code: string
  message: string
}

export interface CaseSubmissionFields {
  caseName?: string
  caseSummary?: string
  caseNumber?: string
  clientInstanceId?: string
  sessionId?: string
  directoryGrantToken?: string
}

export interface LoadDetailOptions {
  background?: boolean
}

export function resolveWorkbenchError(error: any): WorkbenchError {
  const detail = error?.response?.data?.detail
  if (detail && typeof detail === 'object') {
    return {
      code: typeof detail.code === 'string' ? detail.code : 'WORKBENCH_REQUEST_FAILED',
      message: typeof detail.message === 'string' ? detail.message : '工作台请求未完成，请重试。',
    }
  }
  if (!error?.response) return { code: 'NETWORK_ERROR', message: '无法连接后端服务，请检查服务状态后重试。' }
  return { code: 'WORKBENCH_REQUEST_FAILED', message: '工作台请求未完成，请重试。' }
}

function dataOf<T>(response: { data: { data: T } }): T {
  return response.data.data
}

export function useCaseWorkbench(caseId?: string) {
  const [page, setPage] = useState<CaseListPage>({ items: [], offset: 0, limit: CASE_PAGE_SIZE, has_more: false })
  const [pageLoading, setPageLoading] = useState(false)
  const [pageError, setPageError] = useState<WorkbenchError | null>(null)
  const [detail, setDetail] = useState<CaseDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(Boolean(caseId))
  const [detailError, setDetailError] = useState<WorkbenchError | null>(null)
  const [taskSyncVersion, setTaskSyncVersion] = useState(0)
  const listRequest = useRef(0)
  const detailRequest = useRef(0)

  const loadPage = useCallback(async (offset = 0) => {
    const requestId = ++listRequest.current
    setPageLoading(true)
    setPageError(null)
    try {
      const response = await axios.get<{ data: CaseListPage }>(API_ENDPOINTS.WORKBENCH_CASES, {
        params: { offset, limit: CASE_PAGE_SIZE },
      })
      if (requestId === listRequest.current) setPage(dataOf(response))
      return dataOf(response)
    } catch (error) {
      const failure = resolveWorkbenchError(error)
      if (requestId === listRequest.current) setPageError(failure)
      return null
    } finally {
      if (requestId === listRequest.current) setPageLoading(false)
    }
  }, [])

  const loadDetail = useCallback(async (requestedCaseId = caseId, options: LoadDetailOptions = {}) => {
    if (!requestedCaseId) return null
    const background = options.background === true
    const requestId = ++detailRequest.current
    if (!background) {
      setDetailLoading(true)
      setDetailError(null)
    }
    try {
      const response = await axios.get<{ data: CaseDetail }>(API_ENDPOINTS.WORKBENCH_CASE(requestedCaseId))
      const value = dataOf(response)
      if (requestId === detailRequest.current && requestedCaseId === caseId) setDetail(value)
      return value
    } catch (error) {
      const failure = resolveWorkbenchError(error)
      if (!background && requestId === detailRequest.current && requestedCaseId === caseId) setDetailError(failure)
      return null
    } finally {
      if (!background && requestId === detailRequest.current && requestedCaseId === caseId) setDetailLoading(false)
    }
  }, [caseId])

  useEffect(() => {
    if (caseId) {
      setDetail(null)
      void loadDetail(caseId)
      return
    }
    void loadPage(0)
  }, [caseId, loadDetail, loadPage])

  const submitCase = useCallback(async (sourcePath: string, fields: CaseSubmissionFields = {}) => {
    const request: CaseSubmissionRequest = {
      source_path: sourcePath,
      case_name: fields.caseName || '',
      case_summary: fields.caseSummary || '',
      case_number: fields.caseNumber || null,
      client_instance_id: fields.clientInstanceId || undefined,
      session_id: fields.sessionId || undefined,
      directory_grant_token: fields.directoryGrantToken || undefined,
      source_authorization_enabled: getSourceAuthorizationEnabled(),
    }
    const response = await axios.post<{ data: CaseSubmission }>(API_ENDPOINTS.WORKBENCH_CASES, request)
    const submission = dataOf(response)
    setTaskSyncVersion(version => version + 1)
    setPage(current => current.offset === 0
      ? { ...current, items: [submission.shell, ...current.items.filter(item => item.case_id !== submission.shell.case_id)].slice(0, CASE_PAGE_SIZE) }
      : current)
    void loadPage(page.offset)
    return submission
  }, [loadPage, page.offset])

  const retryCase = useCallback(async (requestedCaseId: string) => {
    const response = await axios.post<{ data: CaseDetail }>(API_ENDPOINTS.WORKBENCH_RETRY(requestedCaseId))
    await loadPage(page.offset)
    setTaskSyncVersion(version => version + 1)
    return dataOf(response)
  }, [loadPage, page.offset])

  const cancelTask = useCallback(async (task: TaskRecord) => {
    const response = await axios.post<{ data: TaskRecord }>(API_ENDPOINTS.WORKBENCH_CANCEL_TASK(task.task_id), {
      expected_revision: task.revision,
    })
    await loadPage(page.offset)
    setTaskSyncVersion(version => version + 1)
    return dataOf(response)
  }, [loadPage, page.offset])

  const archiveTaskDetails = useCallback(async (taskId: string) => {
    const response = await axios.get<{ data: ArchiveTaskPublicDetail }>(
      API_ENDPOINTS.WORKBENCH_ARCHIVE_TASK_DETAILS(taskId),
    )
    return dataOf(response)
  }, [])

  const cancelArchiveTask = useCallback(async (taskId: string) => {
    const detail = await archiveTaskDetails(taskId)
    const response = await axios.post<{ data: ArchiveTaskPublicDetail }>(
      API_ENDPOINTS.WORKBENCH_CANCEL_TASK(taskId),
      { expected_revision: detail.revision },
    )
    await loadPage(page.offset)
    return dataOf(response)
  }, [archiveTaskDetails, loadPage, page.offset])

  const retryArchiveTask = useCallback(async (
    taskId: string, expectedCaseRevision: number,
  ) => {
    const detail = await archiveTaskDetails(taskId)
    const response = await axios.post<{ data: { task: ArchiveTaskPublicDetail } }>(
      API_ENDPOINTS.WORKBENCH_RETRY_ARCHIVE_TASK(taskId),
      { expected_revision: detail.revision, expected_case_revision: expectedCaseRevision },
    )
    await loadPage(page.offset)
    return dataOf(response)
  }, [archiveTaskDetails, loadPage, page.offset])

  const archiveHistory = useCallback(async (requestedCaseId: string) => {
    const response = await axios.get<{ data: ArchiveTaskHistory }>(
      API_ENDPOINTS.WORKBENCH_ARCHIVE_HISTORY(requestedCaseId),
    )
    return dataOf(response)
  }, [])

  const archiveResult = useCallback(async (taskId: string) => {
    const response = await axios.get<{ data: ArchiveTaskResult }>(
      API_ENDPOINTS.WORKBENCH_ARCHIVE_TASK_RESULT(taskId),
    )
    return dataOf(response)
  }, [])

  const checkDelete = useCallback(async (requestedCaseId: string) => {
    const response = await axios.get<{ data: { allowed: boolean; blockers: string[] } }>(
      API_ENDPOINTS.WORKBENCH_DELETE_PREFLIGHT(requestedCaseId),
    )
    return dataOf(response)
  }, [])

  const deleteCase = useCallback(async (requestedCaseId: string) => {
    const response = await axios.delete<{ data: CaseDeletionResult }>(
      API_ENDPOINTS.WORKBENCH_DELETE_CASE(requestedCaseId),
    )
    return dataOf(response)
  }, [])

  return {
    page, pageLoading, pageError, loadPage, submitCase, retryCase, cancelTask, checkDelete, deleteCase,
    archiveTaskDetails, cancelArchiveTask, retryArchiveTask, archiveHistory, archiveResult,
    detail, detailLoading, detailError, reloadDetail: loadDetail, taskSyncVersion,
  }
}
