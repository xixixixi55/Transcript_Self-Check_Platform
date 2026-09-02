import {
  ArrowLeftOutlined, ArrowRightOutlined, EditOutlined, HomeOutlined,
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
  confirmCurrentActionDisabled?: boolean
  canReturnToPrevious?: boolean
  isReviewingPrevious?: boolean
  onReturnToPreviousAction?: () => void
  onReturnToCurrentAction?: () => void
  onOpenFullEditor: () => void
  onBackToWorkbench: () => void
  children: React.ReactNode
}

interface CompletedTurn {
  action: GuidedReviewAction
  reply: string
}

interface SwitchedTurn {
  from: string
  to: string
}

type ActionStatusTone = 'current' | 'pending' | 'warning' | 'system' | 'success'
type MascotMood = 'listening' | 'verifying' | 'warning' | 'complete'
type SplitOrder = 'history-first' | 'conversation-first'

const SPLIT_ORDER_STORAGE_KEY = 'biji.guidedReview.splitOrder'

function readSplitOrderPreference(): SplitOrder {
  if (typeof window === 'undefined') return 'history-first'
  try {
    const stored = window.localStorage.getItem(SPLIT_ORDER_STORAGE_KEY)
    return stored === 'conversation-first' || stored === 'history-first' ? stored : 'history-first'
  } catch {
    return 'history-first'
  }
}

function writeSplitOrderPreference(value: SplitOrder): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(SPLIT_ORDER_STORAGE_KEY, value)
  } catch {
    // The current layout still works when browser storage is unavailable.
  }
}

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

function mascotMood(currentAction: GuidedReviewAction | null, completionActive: boolean): MascotMood {
  if (currentAction && RECOVERY_ACTIONS.has(currentAction.kind)) return 'warning'
  if (currentAction?.kind === 'ready') return 'complete'
  if (completionActive) return 'complete'
  if (currentAction?.kind === 'waiting') return 'verifying'
  return 'listening'
}

export function GuidedReviewView({
  conversationKey, history, currentAction, allActions, hasResponse, onSelectAction,
  onRevisitAction,
  onConfirmCurrentAction, confirmCurrentActionDisabled = false,
  canReturnToPrevious = false, isReviewingPrevious = false,
  onReturnToPreviousAction, onReturnToCurrentAction, onOpenFullEditor, onBackToWorkbench, children,
}: Props) {
  const [openPanel, setOpenPanel] = useState<'pending' | null>(null)
  const [avatarUnavailable, setAvatarUnavailable] = useState(false)
  const [completedTurns, setCompletedTurns] = useState<CompletedTurn[]>([])
  const [completionMoodActive, setCompletionMoodActive] = useState(false)
  const [switchedTurn, setSwitchedTurn] = useState<SwitchedTurn | null>(null)
  const [splitOrder, setSplitOrder] = useState<SplitOrder>(readSplitOrderPreference)
  const [mascotMotionActive, setMascotMotionActive] = useState(() => (
    typeof document === 'undefined' || document.visibilityState !== 'hidden'
  ))
  const previousActionRef = useRef<GuidedReviewAction | null>(currentAction)
  const previousConversationKeyRef = useRef(conversationKey)
  const completedActionIdsRef = useRef(new Set<string>())
  const mascotRef = useRef<HTMLDivElement>(null)
  const openPanelRef = useRef<HTMLDivElement>(null)
  const togglePendingPanel = () => {
    setOpenPanel(current => current === 'pending' ? null : 'pending')
  }
  const swapSplitOrder = () => {
    const nextOrder = splitOrder === 'history-first' ? 'conversation-first' : 'history-first'
    setSplitOrder(nextOrder)
    writeSplitOrderPreference(nextOrder)
  }

  useEffect(() => {
    if (previousConversationKeyRef.current !== conversationKey) {
      previousConversationKeyRef.current = conversationKey
      previousActionRef.current = currentAction
      completedActionIdsRef.current.clear()
      setCompletedTurns([])
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
          }
          setCompletedTurns(turns => [...turns.filter(turn => turn.action.id !== previousAction.id), completed])
          if (!completedActionIdsRef.current.has(previousAction.id)) {
            completedActionIdsRef.current.add(previousAction.id)
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
  }, [completionMoodActive, completedTurns.length])

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
  const pendingActionCount = allActions.filter(action => !['waiting', 'ready'].includes(action.kind)).length
  const revisitableCompletedTurns = completedTurns.filter(turn => (
    !allActions.some(action => action.id === turn.action.id)
  ))
  const confirmTextResponse = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (!currentAction?.advanceOnEnter || event.key !== 'Enter' || event.shiftKey
      || event.altKey || event.ctrlKey || event.metaKey) return
    const target = event.target
    if (!(target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement)) return
    if (event.nativeEvent.isComposing || event.nativeEvent.keyCode === 229) return
    event.preventDefault()
    onConfirmCurrentAction?.()
  }
  const previousStepButton = !isReviewingPrevious && canReturnToPrevious ? (
    <Tooltip title="返回上一步">
      <Button shape="circle" size="large" className="guided-review-icon-action"
        icon={<ArrowLeftOutlined />} aria-label="返回上一步"
        onClick={onReturnToPreviousAction} />
    </Tooltip>
  ) : null
  const currentStepButton = isReviewingPrevious ? (
    <Tooltip title="返回当前步骤">
      <Button shape="circle" size="large" className="guided-review-icon-action"
        icon={<ArrowRightOutlined />} aria-label="返回当前步骤"
        onClick={onReturnToCurrentAction} />
    </Tooltip>
  ) : null

  return (
    <div className="guided-review-view">
      <div className="guided-review-layout-toolbar" aria-label="分栏布局控制">
        <span aria-live="polite">
          {splitOrder === 'history-first' ? 'Word 内容预览在左，对话在右' : '对话在左，Word 内容预览在右'}
        </span>
        <Tooltip title={splitOrder === 'history-first' ? '将对话切换到左侧' : '将 Word 内容预览切换到左侧'}>
          <Button shape="circle" size="large" className="guided-review-icon-action"
            icon={<SwapOutlined />} aria-label="交换 Word 内容预览与对话的位置"
            onClick={swapSplitOrder} />
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
              {!hasResponse && (previousStepButton || currentStepButton) && (
                <div className="guided-review-step-navigation guided-review-step-navigation--standalone"
                  aria-label="步骤导航">
                  <span>{previousStepButton}</span>
                  <span>{currentStepButton}</span>
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
                  {(previousStepButton || currentStepButton || currentAction?.advanceOnEnter) && (
                    <div className="guided-review-step-navigation" aria-label="步骤导航">
                      <span className="guided-review-step-navigation__previous">{previousStepButton}</span>
                      <span className="guided-review-step-navigation__next">
                        {currentStepButton}
                        {currentAction?.advanceOnEnter && (
                          <Tooltip title="确认并进入下一步">
                            <Button
                              shape="circle"
                              className="guided-review-icon-action guided-review-card__confirm-action"
                              icon={<ArrowRightOutlined />}
                              aria-label="确认并进入下一步"
                              disabled={confirmCurrentActionDisabled}
                              onClick={onConfirmCurrentAction} />
                          </Tooltip>
                        )}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </article>
          </div>
        </div>
        <div className="guided-review-conversation__utilities">
          <div className="guided-review-tools" aria-label="其他审核操作">
            <Tooltip title="查看并修改已填内容与待办">
              <Badge count={pendingActionCount} size="small" offset={[-2, 2]}>
                <Button shape="circle" size="large" className="guided-review-icon-action guided-review-tools__icon-button"
                  icon={<UnorderedListOutlined />}
                  aria-label={`查看已填内容与待办（${pendingActionCount} 项待处理）`}
                  aria-expanded={openPanel === 'pending'} aria-controls="guided-review-pending-panel"
                  onClick={togglePendingPanel} />
              </Badge>
            </Tooltip>
            <Tooltip title="返回案件工作台">
              <Button shape="circle" size="large" className="guided-review-icon-action guided-review-tools__icon-button"
                icon={<HomeOutlined />} aria-label="返回案件工作台" onClick={onBackToWorkbench} />
            </Tooltip>
          </div>
          {openPanel === 'pending' && (
            <div ref={openPanelRef} id="guided-review-pending-panel" className="guided-review-popover-panel"
              role="region" aria-label="已填内容与待办" tabIndex={-1}>
              <section className="guided-review-action-group" aria-labelledby="guided-review-pending-heading">
                <h3 id="guided-review-pending-heading">待处理与状态</h3>
                {allActions.length ? allActions.map(action => {
                  const isCurrent = action.id === currentAction?.id
                  const status = actionStatus(action, isCurrent)
                  return (
                    <Button type="text" block key={action.id}
                      aria-current={isCurrent ? 'true' : undefined}
                      className={isCurrent ? 'guided-review-action--current' : ''}
                      onClick={() => {
                        onSelectAction(action.id)
                        setOpenPanel(null)
                      }}>
                      <span className="guided-review-action__title-row">
                        <span>{action.title}</span>
                        <span className={`guided-review-action__status guided-review-status--${status.tone}`}>
                          {status.label}
                        </span>
                      </span>
                    </Button>
                  )
                }) : <p>当前没有待处理事项。</p>}
              </section>
              {revisitableCompletedTurns.length > 0 && (
                <section className="guided-review-action-group" aria-labelledby="guided-review-completed-heading">
                  <h3 id="guided-review-completed-heading">本次已填写</h3>
                  {revisitableCompletedTurns.map(turn => (
                    <Button type="text" block key={turn.action.id}
                      aria-label={`修改${actionConversationLabel(turn.action)}`}
                      onClick={() => {
                        onRevisitAction?.(turn.action)
                        setOpenPanel(null)
                      }}>
                      <span className="guided-review-action__title-row">
                        <span>{actionConversationLabel(turn.action)}</span>
                        <span className="guided-review-action__status guided-review-status--success">已填写</span>
                      </span>
                    </Button>
                  ))}
                </section>
              )}
              <section className="guided-review-action-group" aria-labelledby="guided-review-all-fields-heading">
                <h3 id="guided-review-all-fields-heading">其他内容</h3>
                <Button type="text" block aria-label="修改其他已填内容"
                  onClick={() => {
                    setOpenPanel(null)
                    onOpenFullEditor()
                  }}>
                  <span className="guided-review-action__title-row">
                    <span className="guided-review-action__label"><EditOutlined />修改其他已填内容</span>
                  </span>
                </Button>
              </section>
            </div>
          )}
        </div>
        </section>
        {splitOrder === 'conversation-first' && <GuidedReviewHistory key="history" items={history} />}
      </div>
    </div>
  )
}
