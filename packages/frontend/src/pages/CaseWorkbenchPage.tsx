// Layer 12: FE_Pages — persistent multi-case workbench entry.
import React, { useCallback, useState } from 'react'
import { Alert, Button, Col, Empty, Input, Pagination, Row, Space, Spin, Typography, message } from 'antd'
import { FolderOpenOutlined, InboxOutlined, ReloadOutlined } from '@ant-design/icons'
import type { ArchiveTaskAction, ArchiveTaskCardSummary } from '@biji/shared/types'
import { CASE_PAGE_SIZE, resolveWorkbenchError, useCaseWorkbench, useTaskRecords } from '../hooks'
import { CaseCard } from '../components/CaseCard'
import { DemoReadinessNotice } from '../components/DemoReadinessNotice'
import { SourceAuthorizationNotice } from '../components/SourceAuthorizationNotice'

const { Paragraph, Title } = Typography

interface Props {
  archiveSummaryFixtures?: readonly ArchiveTaskCardSummary[]
}

export default function CaseWorkbenchPage({ archiveSummaryFixtures }: Props) {
  const workbench = useCaseWorkbench()
  const taskIds = workbench.page.items.map(item => item.parse_task_id)
  const refreshPageAfterTaskSettled = useCallback(() => {
    void workbench.loadPage(workbench.page.offset)
  }, [workbench.loadPage, workbench.page.offset])
  const { records: tasks, archiveSummariesByCase, error: taskError } = useTaskRecords(taskIds, {
    onTaskStatusChange: refreshPageAfterTaskSettled,
    refreshKey: workbench.taskSyncVersion,
    archiveSummaryFixtures,
  })
  const [submitBusy, setSubmitBusy] = useState(false)
  const [actionCaseId, setActionCaseId] = useState<string | null>(null)
  const [caseName, setCaseName] = useState('')
  const [caseNumber, setCaseNumber] = useState('')
  const [sourcePath, setSourcePath] = useState('')

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

  const handleArchiveAction = (action: ArchiveTaskAction) => {
    const labels: Record<ArchiveTaskAction, string> = {
      cancel: '取消归档', retry: '重试归档', view_result: '查看结果', view_details: '查看归档详情',
    }
    message.info(`${labels[action]}将在 T015 接入真实接口。`)
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
      <SourceAuthorizationNotice />
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
              onArchiveAction={handleArchiveAction}
              onArchivePrecheck={() => message.info('归档前检查将在后续归档接口阶段接入。')}
              actionBusy={actionCaseId === shell.case_id}
            />
          </Col>)}
        </Row>
      ) : <div className="case-workbench-page__empty"><Empty image={<InboxOutlined />} description="还没有案件，登记报告目录后会立即出现案件卡片。"><Button type="primary" icon={<FolderOpenOutlined />} loading={submitBusy} onClick={() => { void submit() }}>登记第一个报告目录</Button></Empty></div>}

      {total > 0 && <div className="case-workbench-page__pagination"><Pagination current={workbench.page.offset / CASE_PAGE_SIZE + 1} pageSize={CASE_PAGE_SIZE} total={total} showSizeChanger={false} onChange={pageNumber => { void workbench.loadPage((pageNumber - 1) * CASE_PAGE_SIZE) }} /></div>}
    </div>
  )
}
