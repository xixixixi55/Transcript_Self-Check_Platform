import {
  ArrowLeftOutlined, CheckCircleOutlined, EditOutlined, FileDoneOutlined,
  SafetyCertificateOutlined, UnorderedListOutlined,
} from '@ant-design/icons'
import { Badge, Button, Tooltip } from 'antd'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type {
  GuidedReviewAction, GuidedReviewActionKind, GuidedReviewHistoryItem,
} from '../hooks/useGuidedReviewCards'
import { GuidedReviewHistory } from './GuidedReviewHistory'

const xiezhiAssistantImage = new URL('./xiezhi-assistant.png', import.meta.url).href

interface Props {
  conversationKey: string
  history: GuidedReviewHistoryItem[]
  currentAction: GuidedReviewAction | null
  allActions: GuidedReviewAction[]
  hasResponse: boolean
  onSelectAction: (actionId: string) => void
  onConfirmCurrentAction?: () => void
  summary: React.ReactNode
  onOpenFullEditor: () => void
  onBackToWorkbench: () => void
  children: React.ReactNode
}

interface CompletedTurn {
  actionId: string
  reply: string
}

type ActionStatusTone = 'current' | 'pending' | 'warning' | 'system' | 'success'

interface ActionStatus {
  label: string
  tone: ActionStatusTone
}

const RECOVERY_ACTIONS = new Set<GuidedReviewActionKind>([
  'source_recovery', 'lease_recovery', 'save_recovery', 'photo_recovery',
])
const HISTORY_READING_THRESHOLD = 4

function conversationTopInScrollRegion(scrollRegion: HTMLElement, conversation: HTMLElement): number {
  return conversation.getBoundingClientRect().top
    - scrollRegion.getBoundingClientRect().top
    + scrollRegion.scrollTop
}

function assistantStatus(currentAction: GuidedReviewAction | null, allActions: GuidedReviewAction[]): ActionStatus {
  if (currentAction?.kind === 'waiting') return { label: '后台处理中', tone: 'system' }
  if (currentAction?.kind === 'ready') return { label: '可生成笔录', tone: 'success' }
  const actionableCount = allActions.filter(action => !['waiting', 'ready'].includes(action.kind)).length
  return actionableCount > 0
    ? { label: `${actionableCount} 项待处理`, tone: 'pending' }
    : { label: '正在整理', tone: 'system' }
}

function actionStatus(action: GuidedReviewAction, isCurrent: boolean): ActionStatus {
  if (isCurrent) return { label: '当前', tone: 'current' }
  if (action.kind === 'waiting') return { label: '后台中', tone: 'system' }
  if (action.kind === 'ready') return { label: '可生成', tone: 'success' }
  if (RECOVERY_ACTIONS.has(action.kind)) return { label: '需恢复', tone: 'warning' }
  if (action.kind === 'archive_decision') return { label: '待选择', tone: 'warning' }
  return { label: '待处理', tone: 'pending' }
}

function completedReply(action: GuidedReviewAction): string | null {
  if (action.kind === 'pending_item') return `${action.pendingItem?.fieldLabel || '当前事项'}已填写`
  if (action.kind === 'archive_decision') return '已选择压缩处理方式'
  if (action.kind === 'save_recovery') return '草稿保存已恢复'
  if (action.kind === 'lease_recovery') return '编辑权限已恢复'
  if (action.kind === 'source_recovery') return '报告来源已重新选择'
  if (action.kind === 'photo_recovery') return '图片保存问题已处理'
  return null
}

function assistantHandoff(reply: string, nextAction: GuidedReviewAction | null): string {
  if (!nextAction) return `已确认：${reply}。当前需要办理的事项已经处理完毕。`
  if (nextAction.kind === 'waiting') return `已确认：${reply}。后台任务还在继续，我会在这里同步进展。`
  if (nextAction.kind === 'ready') return `已确认：${reply}。所需事项已经齐备，可以进行最后生成。`
  return `已确认：${reply}。接下来，${nextAction.title.replace(/[。！？!?]$/, '')}。`
}

export function GuidedReviewView({
  conversationKey, history, currentAction, allActions, hasResponse, onSelectAction, summary,
  onConfirmCurrentAction, onOpenFullEditor, onBackToWorkbench, children,
}: Props) {
  const [openPanel, setOpenPanel] = useState<'pending' | 'summary' | null>(null)
  const [avatarUnavailable, setAvatarUnavailable] = useState(false)
  const [completedTurn, setCompletedTurn] = useState<CompletedTurn | null>(null)
  const previousActionRef = useRef<GuidedReviewAction | null>(currentAction)
  const previousConversationKeyRef = useRef(conversationKey)
  const scrollRegionRef = useRef<HTMLDivElement>(null)
  const conversationRef = useRef<HTMLElement>(null)
  const positionedConversationKeyRef = useRef<string | null>(null)
  const previousHistoryLengthRef = useRef(history.length)
  const viewingHistoryRef = useRef(false)
  const conversationViewportOffsetRef = useRef(0)
  const togglePanel = (panel: 'pending' | 'summary') => {
    setOpenPanel(current => current === panel ? null : panel)
  }

  useEffect(() => {
    if (previousConversationKeyRef.current !== conversationKey) {
      previousConversationKeyRef.current = conversationKey
      previousActionRef.current = currentAction
      setCompletedTurn(null)
      return
    }

    const previousAction = previousActionRef.current
    if (previousAction && previousAction.id !== currentAction?.id) {
      const previousStillPending = allActions.some(action => action.id === previousAction.id)
      const reply = previousStillPending ? null : completedReply(previousAction)
      setCompletedTurn(reply ? { actionId: previousAction.id, reply } : null)
    }
    previousActionRef.current = currentAction
  }, [allActions, conversationKey, currentAction])

  useLayoutEffect(() => {
    const scrollRegion = scrollRegionRef.current
    const conversation = conversationRef.current
    if (!scrollRegion || !conversation) return

    const conversationChanged = positionedConversationKeyRef.current !== conversationKey
    const historyChanged = previousHistoryLengthRef.current !== history.length
    const conversationTop = conversationTopInScrollRegion(scrollRegion, conversation)
    if (conversationChanged) {
      scrollRegion.scrollTop = conversationTop
      viewingHistoryRef.current = false
      conversationViewportOffsetRef.current = 0
    } else if (historyChanged && !viewingHistoryRef.current) {
      scrollRegion.scrollTop = conversationTop + conversationViewportOffsetRef.current
    }
    positionedConversationKeyRef.current = conversationKey
    previousHistoryLengthRef.current = history.length
  }, [conversationKey, history.length])

  const rememberScrollPosition = () => {
    const scrollRegion = scrollRegionRef.current
    const conversation = conversationRef.current
    if (!scrollRegion || !conversation) return
    const conversationTop = conversationTopInScrollRegion(scrollRegion, conversation)
    viewingHistoryRef.current = scrollRegion.scrollTop < conversationTop - HISTORY_READING_THRESHOLD
    if (!viewingHistoryRef.current) {
      conversationViewportOffsetRef.current = Math.max(0, scrollRegion.scrollTop - conversationTop)
    }
  }

  const responseLabel = currentAction?.kind === 'pending_item' ? '你的回复' : '请选择操作'
  const assistantState = assistantStatus(currentAction, allActions)
  const confirmTextResponse = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (!currentAction?.advanceOnEnter || event.key !== 'Enter' || event.shiftKey
      || event.altKey || event.ctrlKey || event.metaKey) return
    const target = event.target
    if (!(target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement)) return
    if (event.nativeEvent.isComposing || event.nativeEvent.keyCode === 229) return
    event.preventDefault()
    onConfirmCurrentAction?.()
  }

  return (
    <div className="guided-review-view">
      <div ref={scrollRegionRef} className="guided-review-scroll" role="region"
        aria-label="审核对话与历史处理轨迹" tabIndex={0} onScroll={rememberScrollPosition}>
        <GuidedReviewHistory items={history} />
        <section ref={conversationRef} className="guided-review-conversation" role="region" aria-label="当前对话">
        <div className="guided-review-conversation__body">
          <div className="guided-review-conversation__mascot" aria-hidden>
            {avatarUnavailable ? <SafetyCertificateOutlined /> : (
              <img src={xiezhiAssistantImage} alt="" width={256} height={256}
                draggable={false} onError={() => setAvatarUnavailable(true)} />
            )}
          </div>
          <div className="guided-review-conversation__content">
            <article className="guided-review-card">
              {completedTurn && (
                <div className="guided-review-turn" aria-label="上一轮办理结果">
                  <div className="guided-review-turn__user">
                    <span>你已完成</span>
                    <p>{completedTurn.reply}</p>
                  </div>
                </div>
              )}
              <div className="guided-review-card__assistant">
                <div className="guided-review-card__assistant-body">
                  <div className="guided-review-conversation__identity">
                    <h2 id="guided-review-conversation-title" tabIndex={-1}>獬豸助手</h2>
                    <span className={`guided-review-conversation__status guided-review-status--${assistantState.tone}`}>
                      {currentAction?.kind === 'waiting' && <span className="guided-review-conversation__pulse" aria-hidden />}
                      {assistantState.label}
                    </span>
                  </div>
                  {completedTurn && (
                    <p className="guided-review-turn__acknowledgement">
                      <CheckCircleOutlined aria-hidden />
                      <span>{assistantHandoff(completedTurn.reply, currentAction)}</span>
                    </p>
                  )}
                  <div key={currentAction?.id || 'guided-review-empty'} className="guided-review-card__message" role="status"
                    aria-label="獬豸助手提示" aria-atomic="true">
                    <h3>{currentAction?.title || '请稍候，正在整理下一步'}</h3>
                    <p className="guided-review-card__description">{currentAction?.description || '当前没有需要立即处理的事项。'}</p>
                  </div>
                </div>
              </div>
              {hasResponse && (
                <div className="guided-review-card__response" role="group" aria-label={responseLabel}
                  onFocusCapture={() => {
                    if (currentAction?.advanceOnEnter) onSelectAction(currentAction.id)
                  }}
                  onKeyDown={confirmTextResponse}>
                  <span className="guided-review-card__response-label">{responseLabel}</span>
                  {children}
                </div>
              )}
            </article>
          </div>
        </div>
        <div className="guided-review-conversation__utilities">
          <div className="guided-review-tools" aria-label="其他审核操作">
            <Tooltip title={`查看全部当前事项（${allActions.length}）`}>
              <Badge count={allActions.length} size="small" offset={[-2, 2]}>
                <Button shape="circle" size="large" className="guided-review-tools__icon-button"
                  icon={<UnorderedListOutlined />} aria-label={`查看全部当前事项（${allActions.length}）`}
                  aria-expanded={openPanel === 'pending'} aria-controls="guided-review-pending-panel"
                  onClick={() => togglePanel('pending')} />
              </Badge>
            </Tooltip>
            <Tooltip title="查看已整理信息">
              <Button shape="circle" size="large" className="guided-review-tools__icon-button" icon={<FileDoneOutlined />}
                aria-label="查看已整理信息" aria-expanded={openPanel === 'summary'}
                aria-controls="guided-review-summary-panel" onClick={() => togglePanel('summary')} />
            </Tooltip>
            <Tooltip title="完整审核编辑">
              <Button type="primary" shape="circle" size="large" className="guided-review-tools__icon-button" icon={<EditOutlined />}
                aria-label="完整审核编辑" onClick={onOpenFullEditor} />
            </Tooltip>
            <Tooltip title="返回案件列表">
              <Button shape="circle" size="large" className="guided-review-tools__icon-button" icon={<ArrowLeftOutlined />}
                aria-label="返回案件列表" onClick={onBackToWorkbench} />
            </Tooltip>
          </div>
          {openPanel === 'pending' && (
            <div id="guided-review-pending-panel" className="guided-review-popover-panel" aria-label="全部当前事项">
              {allActions.length ? allActions.map(action => {
                const isCurrent = action.id === currentAction?.id
                const status = actionStatus(action, isCurrent)
                return (
                  <Button type="text" block key={action.id}
                    aria-current={isCurrent ? 'true' : undefined}
                    className={isCurrent ? 'guided-review-action--current' : ''}
                    onClick={() => onSelectAction(action.id)}>
                    <span className="guided-review-action__title-row">
                      <span>{action.title}</span>
                      <span className={`guided-review-action__status guided-review-status--${status.tone}`}>
                        {status.label}
                      </span>
                    </span>
                    <small>{action.description}</small>
                  </Button>
                )
              }) : <p>当前没有可展示事项。</p>}
            </div>
          )}
          {openPanel === 'summary' && (
            <div id="guided-review-summary-panel" className="guided-review-popover-panel guided-review-summary" aria-label="已整理信息">
              {summary || <p>当前还没有可展示的整理摘要。</p>}
            </div>
          )}
        </div>
        </section>
      </div>
    </div>
  )
}
