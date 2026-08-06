// Layer 12: FE_Pages — persistent multi-case workbench entry.
import React, { useCallback, useState } from 'react'
import { Alert, Button, Col, Modal, Pagination, Row, Space, Spin, Typography, message } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import type {
  ArchiveTaskAction, ArchiveTaskHistory, ArchiveTaskPublicDetail,
  ArchiveTaskResult, CaseShell,
} from '@biji/shared/types'
import { API_ENDPOINTS } from '@biji/shared/constants'
import { CASE_PAGE_SIZE, resolveWorkbenchError, useCaseWorkbench, useTaskRecords } from '../hooks'
import { CaseCard } from '../components/CaseCard'
import { CaseWorkbenchDirectoryPickerCard } from '../components/CaseWorkbenchDirectoryPickerCard'
import { DemoReadinessNotice } from '../components/DemoReadinessNotice'

const { Paragraph, Title } = Typography

export default function CaseWorkbenchPage() {
  const workbench = useCaseWorkbench()
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
  const [submitBusy, setSubmitBusy] = useState(false)
  const [actionCaseId, setActionCaseId] = useState<string | null>(null)
  const [deleteCaseId, setDeleteCaseId] = useState<string | null>(null)
  const [archiveDetail, setArchiveDetail] = useState<ArchiveTaskPublicDetail | null>(null)
  const [archiveHistory, setArchiveHistory] = useState<ArchiveTaskHistory | null>(null)
  const [archiveResult, setArchiveResult] = useState<ArchiveTaskResult | null>(null)

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
    if (!deleteCaseId || actionCaseId) return
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
      } else if (action === 'view_result') {
        setArchiveResult(await workbench.archiveResult(taskId))
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

  return (
    <div className="case-workbench-page">
      <div className="platform-page__eyebrow">案件工作台</div>
      <Title level={1}>电子数据检查案件</Title>
      <Paragraph className="platform-page__description">案件提交、解析、审核和后台任务状态均以服务端持久状态为准；每页最多显示6个案件，上传报告目录入口位于案件卡片末尾、页面未满时显示。</Paragraph>
      <DemoReadinessNotice />
      <div className="case-workbench-page__submission">
        <Button icon={<ReloadOutlined />} onClick={() => workbench.loadPage(workbench.page.offset)} loading={workbench.pageLoading}>刷新</Button>
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
              onArchivePrecheck={() => message.info('请打开案件完成审核，并明确选择立即归档或稍后归档。')}
              actionBusy={actionCaseId === shell.case_id}
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
        title="确认删除吗？"
        okText="确认"
        cancelText="取消"
        confirmLoading={Boolean(deleteCaseId && actionCaseId === deleteCaseId)}
        onOk={() => { void confirmDelete() }}
        onCancel={() => { if (!actionCaseId) setDeleteCaseId(null) }}
      >
        删除后不可恢复，请确认是否删除当前案件。
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
      <Modal
        open={Boolean(archiveResult)}
        title="归档结果"
        footer={null}
        onCancel={() => setArchiveResult(null)}
      >
        {archiveResult && (
          <Space direction="vertical">
            <span>Manifest：{archiveResult.manifest_id}</span>
            <span>已验证分卷：{archiveResult.verified_slots.length}</span>
            <span>正式资产：{archiveResult.assets.length}</span>
            {archiveResult.parts.map(part => (
              <Button
                key={part.part_id}
                href={API_ENDPOINTS.WORKBENCH_ARCHIVE_TASK_RESULT_PART(
                  archiveResult.task_id, part.part_id,
                )}
                download={part.filename}
              >下载 {part.filename}</Button>
            ))}
          </Space>
        )}
      </Modal>
    </div>
  )
}
