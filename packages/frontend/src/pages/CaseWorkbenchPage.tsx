// Layer 12: FE_Pages — persistent multi-case workbench entry.
import React, { useCallback, useState } from 'react'
import { Alert, Button, Col, Empty, Input, Modal, Pagination, Row, Space, Spin, Typography, message } from 'antd'
import { FolderOpenOutlined, InboxOutlined, ReloadOutlined } from '@ant-design/icons'
import type {
  ArchiveTaskAction, ArchiveTaskHistory, ArchiveTaskPublicDetail,
  ArchiveTaskResult, CaseShell,
} from '@biji/shared/types'
import { API_ENDPOINTS } from '@biji/shared/constants'
import { CASE_PAGE_SIZE, resolveWorkbenchError, useCaseWorkbench, useTaskRecords } from '../hooks'
import { CaseCard } from '../components/CaseCard'
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
  const [caseName, setCaseName] = useState('')
  const [caseNumber, setCaseNumber] = useState('')
  const [sourcePath, setSourcePath] = useState('')
  const [archiveDetail, setArchiveDetail] = useState<ArchiveTaskPublicDetail | null>(null)
  const [archiveHistory, setArchiveHistory] = useState<ArchiveTaskHistory | null>(null)
  const [archiveResult, setArchiveResult] = useState<ArchiveTaskResult | null>(null)

  const submit = async () => {
    if (!sourcePath.trim()) { message.warning('请先登记报告目录路径。'); return }
    setSubmitBusy(true)
    try {
      await workbench.submitCase(sourcePath.trim(), { caseName: caseName.trim(), caseNumber: caseNumber.trim() })
      setCaseName(''); setCaseNumber(''); setSourcePath('')
      message.success('案件壳已创建，解析任务已进入工作台。')
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

  const checkDelete = async (caseId: string) => {
    try {
      const result = await workbench.checkDelete(caseId)
      if (!result.allowed) message.warning(`当前案件不可删除：${result.blockers.join('、')}`)
      else message.info('后端已确认可删除；本阶段不提供删除案件记录入口，正式产物不会随卡片操作删除。')
    } catch { message.error('删除条件检查失败，请稍后重试。') }
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
      <Paragraph className="platform-page__description">案件提交、解析、审核和后台任务状态均以服务端持久状态为准；每页最多显示6个案件。</Paragraph>
      <DemoReadinessNotice />
      <Space wrap className="case-workbench-page__toolbar">
        <Input aria-label="报告目录路径" value={sourcePath} onChange={event => setSourcePath(event.target.value)} placeholder="粘贴报告目录的本机绝对路径" />
        <Input aria-label="案件名称" value={caseName} onChange={event => setCaseName(event.target.value)} placeholder="案件名称（可选）" />
        <Input aria-label="案件编号" value={caseNumber} onChange={event => setCaseNumber(event.target.value)} placeholder="案件编号（可选）" />
        <Button type="primary" icon={<FolderOpenOutlined />} loading={submitBusy} onClick={() => { void submit() }}>登记并解析报告目录</Button>
        <Button icon={<ReloadOutlined />} onClick={() => workbench.loadPage(workbench.page.offset)} loading={workbench.pageLoading}>刷新</Button>
      </Space>

      {workbench.pageError && <Alert className="case-workbench-page__toolbar" type="error" showIcon message={workbench.pageError.message} action={<Button onClick={() => workbench.loadPage(workbench.page.offset)}>重试</Button>} />}
      {taskError && <Alert className="case-workbench-page__toolbar" type="warning" showIcon message={taskError.message} action={<Button onClick={() => workbench.loadPage(workbench.page.offset)}>重试</Button>} />}
      {workbench.pageLoading && !workbench.page.items.length ? <Spin size="large" style={{ display: 'block', margin: '80px auto' }} /> : workbench.page.items.length ? (
        <Row gutter={[16, 16]} className="case-workbench-grid">
          {workbench.page.items.map(shell => <Col key={shell.case_id} xs={24} md={12} lg={8}>
            <CaseCard
              shell={shell}
              task={tasks[shell.parse_task_id]}
              archiveSummary={archiveSummariesByCase[shell.case_id]}
              onRetry={() => { void retry(shell.case_id) }}
              onCancel={() => { void cancel(shell.case_id) }}
              onDeleteCheck={() => { void checkDelete(shell.case_id) }}
              onArchiveAction={action => {
                const summary = archiveSummariesByCase[shell.case_id]
                if (summary) void handleArchiveAction(shell, summary.task_id, action)
              }}
              onArchivePrecheck={() => message.info('请打开案件完成审核，并明确选择立即归档或稍后归档。')}
              actionBusy={actionCaseId === shell.case_id}
            />
          </Col>)}
        </Row>
      ) : <div className="case-workbench-page__empty"><Empty image={<InboxOutlined />} description="还没有案件，登记报告目录后会立即出现案件卡片。"><Button type="primary" icon={<FolderOpenOutlined />} loading={submitBusy} onClick={() => { void submit() }}>登记第一个报告目录</Button></Empty></div>}

      {total > 0 && <div className="case-workbench-page__pagination"><Pagination current={workbench.page.offset / CASE_PAGE_SIZE + 1} pageSize={CASE_PAGE_SIZE} total={total} showSizeChanger={false} onChange={pageNumber => { void workbench.loadPage((pageNumber - 1) * CASE_PAGE_SIZE) }} /></div>}
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
