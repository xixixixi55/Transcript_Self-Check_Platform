import {
  ArrowLeftOutlined, ArrowRightOutlined, CheckCircleOutlined, EditOutlined, FileDoneOutlined, HomeOutlined,
  SafetyCertificateOutlined, SwapOutlined, UnorderedListOutlined,
} from '@ant-design/icons'
import { Badge, Button, Tooltip } from 'antd'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type {
  GuidedReviewAction, GuidedReviewActionKind, GuidedReviewHistoryItem,
} from '../hooks/useGuidedReviewCards'
import { GuidedReviewHistory } from './GuidedReviewHistory'

const xiezhiAssistantStatesImage = new URL('./xiezhi-assistant-states.png', import.meta.url).href

interface Props {
  conversationKey: string
  history: GuidedReviewHistoryItem[]
  currentAction: GuidedReviewAction | null
  allActions: GuidedReviewAction[]
  hasResponse: boolean
  onSelectAction: (actionId: string) => void
  onRevisitAction?: (action: GuidedReviewAction) => void
  onConfirmCurrentAction?: () => void
  canReturnToPrevious?: boolean
  isReviewingPrevious?: boolean
  onReturnToPreviousAction?: () => void
  onReturnToCurrentAction?: () => void
  summary: React.ReactNode
  onOpenFullEditor: () => void
  onBackToWorkbench: () => void
  children: React.ReactNode
}

interface CompletedTurn {
  action: GuidedReviewAction
  reply: string
  handoff: string
}

interface SwitchedTurn {
  from: string
  to: string
}

type ActionStatusTone = 'current' | 'pending' | 'warning' | 'system' | 'success'
type MascotMood = 'listening' | 'verifying' | 'warning' | 'complete'
type SplitOrder = 'history-first' | 'conversation-first'

interface ActionStatus {
  label: string
  tone: ActionStatusTone
}

const RECOVERY_ACTIONS = new Set<GuidedReviewActionKind>([
  'source_recovery', 'lease_recovery', 'save_recovery', 'photo_recovery',
])
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

function actionConversationLabel(action: GuidedReviewAction): string {
  if (action.kind === 'pending_item') return action.pendingItem?.fieldLabel || action.title
  if (action.kind === 'archive_decision') return '压缩时机'
  return action.title.replace(/^请(?:先)?/, '').replace(/[。！？!?]$/, '')
}

function assistantHandoff(action: GuidedReviewAction, reply: string, nextAction: GuidedReviewAction | null): string {
  const label = actionConversationLabel(action)
  if (!nextAction) return `${label}已经处理完成。当前需要办理的事项已经全部核对。`
  if (nextAction.kind === 'waiting') {
    return label === '文号'
      ? '文号已经纳入当前笔录。后台任务还在继续，我会同步核对结果。'
      : `${label}已经处理完成。后台任务还在继续，我会同步核对结果。`
  }
  if (nextAction.kind === 'ready') return `${label}已经处理完成。所需事项已经齐备，可以进行最后生成。`
  const nextLabel = actionConversationLabel(nextAction)
  return `${label}已经处理完成。接下来核对${nextLabel}，确保相关内容保持一致。`
}

function mascotMood(currentAction: GuidedReviewAction | null, completionActive: boolean): MascotMood {
  if (currentAction && RECOVERY_ACTIONS.has(currentAction.kind)) return 'warning'
  if (currentAction?.kind === 'ready') return 'complete'
  if (completionActive) return 'complete'
  if (currentAction?.kind === 'waiting') return 'verifying'
  return 'listening'
}

export function GuidedReviewView({
  conversationKey, history, currentAction, allActions, hasResponse, onSelectAction, summary,
  onRevisitAction,
  onConfirmCurrentAction, canReturnToPrevious = false, isReviewingPrevious = false,
  onReturnToPreviousAction, onReturnToCurrentAction, onOpenFullEditor, onBackToWorkbench, children,
}: Props) {
  const [openPanel, setOpenPanel] = useState<'pending' | 'summary' | null>(null)
  const [avatarUnavailable, setAvatarUnavailable] = useState(false)
  const [completedTurns, setCompletedTurns] = useState<CompletedTurn[]>([])
  const [completedTurnCount, setCompletedTurnCount] = useState(0)
  const [completionMoodActive, setCompletionMoodActive] = useState(false)
  const [switchedTurn, setSwitchedTurn] = useState<SwitchedTurn | null>(null)
  const [splitOrder, setSplitOrder] = useState<SplitOrder>('history-first')
  const [mascotMotionActive, setMascotMotionActive] = useState(() => (
    typeof document === 'undefined' || document.visibilityState !== 'hidden'
  ))
  const previousActionRef = useRef<GuidedReviewAction | null>(currentAction)
  const previousConversationKeyRef = useRef(conversationKey)
  const completedActionIdsRef = useRef(new Set<string>())
  const mascotRef = useRef<HTMLDivElement>(null)
  const openPanelRef = useRef<HTMLDivElement>(null)
  const togglePanel = (panel: 'pending' | 'summary') => {
    setOpenPanel(current => current === panel ? null : panel)
  }

  useEffect(() => {
    if (previousConversationKeyRef.current !== conversationKey) {
      previousConversationKeyRef.current = conversationKey
      previousActionRef.current = currentAction
      completedActionIdsRef.current.clear()
      setCompletedTurns([])
      setCompletedTurnCount(0)
      setCompletionMoodActive(false)
      setSwitchedTurn(null)
      return
    }

    const previousAction = previousActionRef.current
    if (previousAction && previousAction.id !== currentAction?.id) {
      const previousStillPending = allActions.some(action => action.id === previousAction.id)
      const switchedToAction = previousStillPending && currentAction
        && !['waiting', 'ready'].includes(currentAction.kind)
      if (switchedToAction) {
        setSwitchedTurn({
          from: actionConversationLabel(previousAction),
          to: actionConversationLabel(currentAction),
        })
      } else {
        const reply = previousStillPending ? null : completedReply(previousAction)
        setSwitchedTurn(null)
        if (reply) {
          const completed = {
            action: previousAction,
            reply,
            handoff: assistantHandoff(previousAction, reply, currentAction),
          }
          setCompletedTurns(turns => [...turns.filter(turn => turn.action.id !== previousAction.id), completed].slice(-3))
          if (!completedActionIdsRef.current.has(previousAction.id)) {
            completedActionIdsRef.current.add(previousAction.id)
            setCompletedTurnCount(count => count + 1)
          }
          setCompletionMoodActive(true)
        }
      }
    }
    previousActionRef.current = currentAction
  }, [allActions, conversationKey, currentAction])

  useEffect(() => {
    if (!completionMoodActive) return
    const timer = window.setTimeout(() => setCompletionMoodActive(false), 1800)
    return () => window.clearTimeout(timer)
  }, [completionMoodActive, completedTurnCount])

  useEffect(() => {
    const mascot = mascotRef.current
    if (!mascot) return

    let inViewport = true
    const syncMotionState = () => {
      setMascotMotionActive(document.visibilityState !== 'hidden' && inViewport)
    }
    const observer = typeof IntersectionObserver === 'undefined' ? null : new IntersectionObserver(([entry]) => {
      inViewport = entry?.isIntersecting ?? true
      syncMotionState()
    }, { threshold: 0.05 })

    observer?.observe(mascot)
    document.addEventListener('visibilitychange', syncMotionState)
    syncMotionState()
    return () => {
      observer?.disconnect()
      document.removeEventListener('visibilitychange', syncMotionState)
    }
  }, [])

  useLayoutEffect(() => {
    if (!openPanel) return
    const panel = openPanelRef.current
    if (!panel) return
    panel.focus({ preventScroll: true })
    panel.scrollIntoView({ block: 'nearest', inline: 'nearest' })
  }, [openPanel])

  const responseLabel = currentAction?.kind === 'pending_item' ? '你的回复' : '请选择操作'
  const assistantState = assistantStatus(currentAction, allActions)
  const currentMascotMood = mascotMood(currentAction, completionMoodActive)
  const hiddenCompletedTurnCount = Math.max(0, completedTurnCount - completedTurns.length)
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
      <div className="guided-review-layout-toolbar" aria-label="分栏布局控制">
        <span aria-live="polite">
          {splitOrder === 'history-first' ? 'Word 内容预览在左，对话在右' : '对话在左，Word 内容预览在右'}
        </span>
        <Tooltip title={splitOrder === 'history-first' ? '将对话切换到左侧' : '将 Word 内容预览切换到左侧'}>
          <Button shape="circle" size="large" className="guided-review-icon-action"
            icon={<SwapOutlined />} aria-label="交换 Word 内容预览与对话的位置"
            onClick={() => setSplitOrder(current => (
              current === 'history-first' ? 'conversation-first' : 'history-first'
            ))} />
        </Tooltip>
      </div>
      <div className={`guided-review-scroll guided-review-scroll--${splitOrder}`} role="group"
        aria-label="獬豸助手分栏">
        {splitOrder === 'history-first' && <GuidedReviewHistory key="history" items={history} />}
        <section key="conversation" className="guided-review-conversation" role="region" aria-label="当前对话">
        <div className="guided-review-conversation__body">
          <div ref={mascotRef}
            className={`guided-review-conversation__mascot${mascotMotionActive ? ' is-motion-active' : ''}`}
            data-motion-state={mascotMotionActive ? 'active' : 'paused'} data-mood={currentMascotMood} aria-hidden>
            <span key={currentAction?.id || 'guided-review-empty'}
              className="guided-review-conversation__mascot-figure" data-action-id={currentAction?.id}
              data-mood={currentMascotMood}>
              {avatarUnavailable ? <SafetyCertificateOutlined /> : (
                <span className="guided-review-conversation__mascot-sprite">
                  <img src={xiezhiAssistantStatesImage} alt="" width={1536} height={1536}
                    draggable={false} onError={() => setAvatarUnavailable(true)} />
                </span>
              )}
            </span>
          </div>
          <div className="guided-review-conversation__content">
            <article className="guided-review-card">
              {hiddenCompletedTurnCount > 0 && (
                <p className="guided-review-turn__collapsed">更早已完成 {hiddenCompletedTurnCount} 项</p>
              )}
              {completedTurns.map((turn, index) => (
                <div key={turn.action.id} className="guided-review-turn"
                  aria-label={index === completedTurns.length - 1 ? '上一轮办理结果' : '较早办理结果'}>
                  <div className="guided-review-turn__user">
                    <span>你已完成</span>
                    <p>{turn.reply}</p>
                  </div>
                  <div className="guided-review-turn__assistant-summary">
                    <CheckCircleOutlined aria-hidden />
                    <span>{turn.handoff}</span>
                    <Tooltip title={`修改${actionConversationLabel(turn.action)}`}>
                      <Button shape="circle" size="large" className="guided-review-icon-action"
                        icon={<EditOutlined />} aria-label={`修改${actionConversationLabel(turn.action)}`}
                        onClick={() => onRevisitAction?.(turn.action)} />
                    </Tooltip>
                  </div>
                </div>
              ))}
              <div className="guided-review-card__assistant">
                <div className="guided-review-card__assistant-body">
                  <div className="guided-review-conversation__identity">
                    <h2 id="guided-review-conversation-title" tabIndex={-1}>獬豸助手</h2>
                    <span className={`guided-review-conversation__status guided-review-status--${assistantState.tone}`}>
                      {currentAction?.kind === 'waiting' && <span className="guided-review-conversation__pulse" aria-hidden />}
                      {assistantState.label}
                    </span>
                  </div>
                  {switchedTurn && (
                    <p className="guided-review-turn__acknowledgement guided-review-turn__acknowledgement--switch"
                      aria-label="事项切换说明">
                      <SwapOutlined aria-hidden />
                      <span>{`好的，先处理“${switchedTurn.to}”。“${switchedTurn.from}”仍保留在待办中，之后可以继续。`}</span>
                    </p>
                  )}
                  <div key={currentAction?.id || 'guided-review-empty'} className="guided-review-card__message" role="status"
                    aria-label="獬豸助手提示" aria-atomic="true">
                    <h3>{currentAction?.title || '请稍候，正在整理下一步'}</h3>
                    <p className="guided-review-card__description">{currentAction?.description || '当前没有需要立即处理的事项。'}</p>
                  </div>
                </div>
              </div>
              {(canReturnToPrevious || isReviewingPrevious) && (
                <div className="guided-review-step-navigation" aria-label="步骤导航">
                  {isReviewingPrevious ? (
                    <Tooltip title="返回当前步骤">
                      <Button shape="circle" size="large" className="guided-review-icon-action"
                        icon={<ArrowRightOutlined />} aria-label="返回当前步骤"
                        onClick={onReturnToCurrentAction} />
                    </Tooltip>
                  ) : (
                    <Tooltip title="返回上一步">
                      <Button shape="circle" size="large" className="guided-review-icon-action"
                        icon={<ArrowLeftOutlined />} aria-label="返回上一步"
                        onClick={onReturnToPreviousAction} />
                    </Tooltip>
                  )}
                </div>
              )}
              {hasResponse && (
                <div key={`response-${currentAction?.id || 'empty'}`} data-action-id={currentAction?.id}
                  className="guided-review-card__response" role="group" aria-label={responseLabel}
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
                <Button shape="circle" size="large" className="guided-review-icon-action guided-review-tools__icon-button"
                  icon={<UnorderedListOutlined />} aria-label={`查看全部当前事项（${allActions.length}）`}
                  aria-expanded={openPanel === 'pending'} aria-controls="guided-review-pending-panel"
                  onClick={() => togglePanel('pending')} />
              </Badge>
            </Tooltip>
            <Tooltip title="查看已整理信息">
              <Button shape="circle" size="large" className="guided-review-icon-action guided-review-tools__icon-button"
                icon={<FileDoneOutlined />} aria-label="查看已整理信息"
                aria-expanded={openPanel === 'summary'} aria-controls="guided-review-summary-panel"
                onClick={() => togglePanel('summary')} />
            </Tooltip>
            <Tooltip title="完整审核编辑">
              <Button type="primary" shape="circle" size="large"
                className="guided-review-icon-action guided-review-tools__icon-button guided-review-tools__primary"
                icon={<EditOutlined />} aria-label="完整审核编辑" onClick={onOpenFullEditor} />
            </Tooltip>
            <Tooltip title="返回案件工作台">
              <Button shape="circle" size="large" className="guided-review-icon-action guided-review-tools__icon-button"
                icon={<HomeOutlined />} aria-label="返回案件工作台" onClick={onBackToWorkbench} />
            </Tooltip>
          </div>
          {openPanel === 'pending' && (
            <div ref={openPanelRef} id="guided-review-pending-panel" className="guided-review-popover-panel"
              role="region" aria-label="全部当前事项" tabIndex={-1}>
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
            <div ref={openPanelRef} id="guided-review-summary-panel"
              className="guided-review-popover-panel guided-review-summary"
              role="region" aria-label="已整理信息" tabIndex={-1}>
              {summary || <p>当前还没有可展示的整理摘要。</p>}
            </div>
          )}
        </div>
        </section>
        {splitOrder === 'conversation-first' && <GuidedReviewHistory key="history" items={history} />}
      </div>
    </div>
  )
}
