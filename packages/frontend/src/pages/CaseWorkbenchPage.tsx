// Layer 12: FE_Pages — persistent multi-case workbench entry.
import React, { useCallback, useState } from 'react'
import { Alert, Button, Col, Modal, Pagination, Row, Space, Spin, Tooltip, Typography, message } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import type {
  ArchiveCompletionStatus, ArchiveTaskAction, ArchiveTaskHistory,
  ArchiveTaskPublicDetail, ArchiveTaskResult, CaseShell,
} from '@biji/shared/types'
import { API_ENDPOINTS } from '@biji/shared/constants'
import { allPartsDiscMapped, resolveArchiveCompletionStatus } from '@biji/shared/utils'
import { CASE_PAGE_SIZE, resolveWorkbenchError, useCaseWorkbench, useSourceAuthorizationPreference, useTaskRecords } from '../hooks'
import { useArchiveCompletion } from '../hooks/useArchiveCompletion'
import { useArchiveCompletionStatuses } from '../hooks/useArchiveCompletionStatuses'
import { CaseCard } from '../components/CaseCard'
import { CaseWorkbenchDirectoryPickerCard } from '../components/CaseWorkbenchDirectoryPickerCard'
import { WordDownloadNameDialog } from '../components/WordDownloadNameDialog'

const { Title } = Typography

function completionStatusFor(
  shell: CaseShell, result: ArchiveTaskResult | null,
): ArchiveCompletionStatus | undefined {
  if (shell.lifecycle === 'exported') return 'exported'
  if (shell.lifecycle !== 'archive_verified') return undefined
  if (result && result.case_id === shell.case_id) {
    return resolveArchiveCompletionStatus(shell.lifecycle, allPartsDiscMapped(result.parts)) ?? undefined
  }
  return undefined
}

export default function CaseWorkbenchPage() {
  const workbench = useCaseWorkbench()
  const sourceAuthorization = useSourceAuthorizationPreference()
  const taskIds = workbench.page.items.map(item => item.parse_task_id)
  const refreshPageAfterTaskSettled = useCallback(() => {
    void workbench.loadPage(workbench.page.offset)
  }, [workbench.loadPage, workbench.page.offset])
  const { records: tasks, archiveSummariesByCase, error: taskError } = useTaskRecords(taskIds, {
    onTaskStatusChange: refreshPageAfterTaskSettled,
    onPoll: async () => { await workbench.loadPage(workbench.page.offset) },
    refreshKey: workbench.taskSyncVersion,
    cases: workbench.page.items,
  })
  const completionResults = useArchiveCompletionStatuses(
    workbench.page.items, archiveSummariesByCase, workbench.archiveResult,
  )
  const archiveCompletion = useArchiveCompletion()
  const [submitBusy, setSubmitBusy] = useState(false)
  const [actionCaseId, setActionCaseId] = useState<string | null>(null)
  const [exportingCaseId, setExportingCaseId] = useState<string | null>(null)
  const [deleteCaseId, setDeleteCaseId] = useState<string | null>(null)
  const [archiveDetail, setArchiveDetail] = useState<ArchiveTaskPublicDetail | null>(null)
  const [archiveHistory, setArchiveHistory] = useState<ArchiveTaskHistory | null>(null)
  const [exportNameCaseId, setExportNameCaseId] = useState<string | null>(null)

  const submit = async () => {
    setSubmitBusy(true)
    try {
      const submission = await workbench.selectDirectoryAndSubmitCase()
      if (submission) {
        message.success('案件壳已创建，解析任务已进入工作台。')
      }
    } catch (error) {
      message.error(resolveWorkbenchError(error).message)
    } finally { setSubmitBusy(false) }
  }

  const retry = async (caseId: string) => {
    setActionCaseId(caseId)
    try { await workbench.retryCase(caseId); message.success('解析已重新排队。') }
    catch { message.error('解析重试未完成，请稍后重试。') }
    finally { setActionCaseId(null) }
  }

  const cancel = async (caseId: string) => {
    const task = tasks[workbench.page.items.find(item => item.case_id === caseId)?.parse_task_id || '']
    if (!task) return
    setActionCaseId(caseId)
    try { await workbench.cancelTask(task); message.info('已向后端提交取消请求，状态以任务记录为准。') }
    catch { message.error('取消请求未完成，请刷新后重试。') }
    finally { setActionCaseId(null) }
  }

  const confirmDelete = async () => {
    if (!deleteCaseId || actionCaseId === deleteCaseId) return
    const requestedCaseId = deleteCaseId
    setActionCaseId(requestedCaseId)
    try {
      await workbench.deleteCase(requestedCaseId)
      const nextOffset = workbench.page.items.length === 1 && workbench.page.offset > 0
        ? Math.max(0, workbench.page.offset - CASE_PAGE_SIZE)
        : workbench.page.offset
      setDeleteCaseId(null)
      await workbench.loadPage(nextOffset)
      message.success('案件已删除。')
    } catch (error) {
      message.error(resolveWorkbenchError(error).message)
    } finally {
      setActionCaseId(null)
    }
  }

  const exportCase = (shell: CaseShell) => {
    if (actionCaseId) return
    setExportNameCaseId(shell.case_id)
  }

  const confirmExportName = async (wordFileName: string) => {
    const shell = workbench.page.items.find(item => item.case_id === exportNameCaseId)
    setExportNameCaseId(null)
    if (!shell || actionCaseId) return
    setActionCaseId(shell.case_id)
    setExportingCaseId(shell.case_id)
    try {
      const chosen = await archiveCompletion.chooseDirectory()
      if ('cancelled' in chosen) return
      const summary = archiveSummariesByCase[shell.case_id]
      const cachedArchiveResult = completionResults[shell.case_id]
      const archiveResult = cachedArchiveResult?.task_id === summary?.task_id
        ? cachedArchiveResult
        : summary ? await workbench.archiveResult(summary.task_id) : null
      const result = await archiveCompletion.exportBundle(
        shell.case_id, shell.revision, chosen.path, chosen.token, wordFileName,
        archiveResult?.parts ?? null,
      )
      message.success(`已导出至：${result.output.export_path}`)
      await workbench.loadPage(workbench.page.offset)
    } catch (error) {
      message.error(resolveWorkbenchError(error).message)
    } finally {
      setActionCaseId(null)
      setExportingCaseId(null)
    }
  }

  const handleArchiveAction = async (
    shell: CaseShell, taskId: string, action: ArchiveTaskAction,
  ) => {
    if (actionCaseId) return
    setActionCaseId(shell.case_id)
    try {
      if (action === 'cancel') {
        await workbench.cancelArchiveTask(taskId)
        message.info('取消请求已提交，最终状态以后端任务记录为准。')
      } else if (action === 'retry') {
        await workbench.retryArchiveTask(taskId, shell.revision)
        message.success('已创建新的归档任务，历史任务保持不变。')
      } else {
        const [detail, history] = await Promise.all([
          workbench.archiveTaskDetails(taskId),
          workbench.archiveHistory(shell.case_id),
        ])
        setArchiveDetail(detail)
        setArchiveHistory(history)
      }
    } catch (error) {
      message.error(resolveWorkbenchError(error).message)
      await workbench.loadPage(workbench.page.offset)
    } finally {
      setActionCaseId(null)
    }
  }

  const total = workbench.page.has_more
    ? workbench.page.offset + workbench.page.items.length + 1
    : workbench.page.offset + workbench.page.items.length
  const deleteShell = workbench.page.items.find(item => item.case_id === deleteCaseId)

  return (
    <div className="case-workbench-page">
      <div className="case-workbench-page__header">
        <div className="case-workbench-page__heading">
          <div className="platform-page__eyebrow">电子数据检查笔录</div>
          <Title level={1}>案件工作台</Title>
        </div>
        <div className="case-workbench-page__submission">
          <Tooltip title={sourceAuthorization.enabled
            ? '已开启，只允许登记已配置或明确授权的来源目录。'
            : '已关闭，可登记满足基础安全检查的本机报告目录。'}>
            <Button
              size="small"
              type={sourceAuthorization.enabled ? 'primary' : 'default'}
              aria-label="来源目录校验"
              aria-pressed={sourceAuthorization.enabled}
              onClick={() => sourceAuthorization.setEnabled(!sourceAuthorization.enabled)}
            >
              来源目录校验：{sourceAuthorization.enabled ? '开' : '关'}
            </Button>
          </Tooltip>
          <Button icon={<ReloadOutlined />} onClick={() => workbench.loadPage(workbench.page.offset)} loading={workbench.pageLoading}>刷新</Button>
        </div>
      </div>

      {workbench.pageError && <Alert className="case-workbench-page__toolbar" type="error" showIcon message={workbench.pageError.message} action={<Button onClick={() => workbench.loadPage(workbench.page.offset)}>重试</Button>} />}
      {taskError && <Alert className="case-workbench-page__toolbar" type="warning" showIcon message={taskError.message} action={<Button onClick={() => workbench.loadPage(workbench.page.offset)}>重试</Button>} />}
      {workbench.pageLoading && !workbench.page.items.length ? <Spin size="large" style={{ display: 'block', margin: '80px auto' }} /> : (
        <Row gutter={[16, 16]} className="case-workbench-grid">
          {workbench.page.items.map(shell => <Col key={shell.case_id} xs={24} md={12} lg={8}>
            <CaseCard
              shell={shell}
              task={tasks[shell.parse_task_id]}
              archiveSummary={archiveSummariesByCase[shell.case_id]}
              onRetry={() => { void retry(shell.case_id) }}
              onCancel={() => { void cancel(shell.case_id) }}
              onDelete={() => setDeleteCaseId(shell.case_id)}
              onArchiveAction={action => {
                const summary = archiveSummariesByCase[shell.case_id]
                if (summary) void handleArchiveAction(shell, summary.task_id, action)
              }}
              actionBusy={actionCaseId === shell.case_id}
              completionStatus={completionStatusFor(shell, completionResults[shell.case_id])}
              onExport={() => { void exportCase(shell) }}
              exporting={exportingCaseId === shell.case_id}
            />
          </Col>)}
          {workbench.page.items.length < CASE_PAGE_SIZE && (
            <Col xs={24} md={12} lg={8}>
              <CaseWorkbenchDirectoryPickerCard loading={submitBusy} onClick={() => { void submit() }} />
            </Col>
          )}
        </Row>
      )}

      {total > 0 && <div className="case-workbench-page__pagination"><Pagination current={workbench.page.offset / CASE_PAGE_SIZE + 1} pageSize={CASE_PAGE_SIZE} total={total} showSizeChanger={false} onChange={pageNumber => { void workbench.loadPage((pageNumber - 1) * CASE_PAGE_SIZE) }} /></div>}
      <Modal
        open={Boolean(deleteCaseId)}
        title="确认删除该案件？"
        okText="确认删除"
        cancelText="取消"
        confirmLoading={Boolean(deleteCaseId && actionCaseId === deleteCaseId)}
        onOk={() => { void confirmDelete() }}
        onCancel={() => { if (!actionCaseId) setDeleteCaseId(null) }}
      >
        {deleteShell?.lifecycle === 'exported'
          ? '案件已成功导出。删除后，该案件将从案件工作台移除。已导出到目标目录的文件不会被删除。'
          : '删除后，该案件将从案件工作台移除，平台内受控数据和文件不可恢复。'}
      </Modal>
      <Modal
        open={Boolean(archiveDetail)}
        title="归档任务详情"
        footer={null}
        onCancel={() => { setArchiveDetail(null); setArchiveHistory(null) }}
      >
        {archiveDetail && (
          <Space direction="vertical">
            <span>状态：{archiveDetail.status}</span>
            <span>阶段：{archiveDetail.stage_label}（{archiveDetail.percent}%）</span>
            {archiveDetail.error_summary && <span>安全摘要：{archiveDetail.error_summary}</span>}
            <span>本案归档历史：{archiveHistory?.items.length ?? 0} 次</span>
            <span>当前计划分卷槽位：{archiveDetail.archive_plan?.volume_slots.length ?? 0}</span>
          </Space>
        )}
      </Modal>
      <WordDownloadNameDialog
        open={Boolean(exportNameCaseId)}
        documentNumber={workbench.page.items.find(item => item.case_id === exportNameCaseId)?.case_name}
        exporting={Boolean(exportingCaseId)}
        onCancel={() => setExportNameCaseId(null)}
        onConfirm={downloadName => { void confirmExportName(downloadName) }}
      />
    </div>
  )
}
