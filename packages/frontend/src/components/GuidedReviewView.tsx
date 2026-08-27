import { SafetyCertificateOutlined } from '@ant-design/icons'
import { Badge, Button } from 'antd'
import { useEffect, useRef, useState } from 'react'
import type { GuidedReviewAction, GuidedReviewHistoryItem } from '../hooks/useGuidedReviewCards'
import { GuidedReviewHistory } from './GuidedReviewHistory'

const xiezhiAssistantImage = new URL('./xiezhi-assistant.png', import.meta.url).href

interface Props {
  conversationKey: string
  history: GuidedReviewHistoryItem[]
  currentAction: GuidedReviewAction | null
  allActions: GuidedReviewAction[]
  hasResponse: boolean
  onSelectAction: (actionId: string) => void
  summary: React.ReactNode
  onOpenFullEditor: () => void
  onBackToWorkbench: () => void
  children: React.ReactNode
}

interface CompletedTurn {
  actionId: string
  reply: string
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

export function GuidedReviewView({
  conversationKey, history, currentAction, allActions, hasResponse, onSelectAction, summary,
  onOpenFullEditor, onBackToWorkbench, children,
}: Props) {
  const [openPanel, setOpenPanel] = useState<'pending' | 'summary' | null>(null)
  const [avatarUnavailable, setAvatarUnavailable] = useState(false)
  const [completedTurn, setCompletedTurn] = useState<CompletedTurn | null>(null)
  const previousActionRef = useRef<GuidedReviewAction | null>(currentAction)
  const previousConversationKeyRef = useRef(conversationKey)
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

  const responseLabel = currentAction?.kind === 'pending_item' ? '你的回复' : '请选择操作'

  return (
    <div className="guided-review-view">
      <GuidedReviewHistory items={history} />
      <section className="guided-review-conversation" role="region" aria-label="当前对话">
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
                <div className="guided-review-turn" aria-label="上一轮回复">
                  <div className="guided-review-turn__user">
                    <span>你的回复</span>
                    <p>{completedTurn.reply}</p>
                  </div>
                </div>
              )}
              <div className="guided-review-card__assistant">
                <div className="guided-review-card__assistant-body">
                  <div className="guided-review-conversation__identity">
                    <h2 id="guided-review-conversation-title" tabIndex={-1}>獬豸助手</h2>
                    <Badge count={allActions.filter(action => action.kind === 'pending_item').length}
                      showZero overflowCount={99} title="需要用户处理的事项数" />
                  </div>
                  {completedTurn && (
                    <p className="guided-review-turn__acknowledgement">已收到，我继续提示下一项。</p>
                  )}
                  <div className="guided-review-card__message" role="status"
                    aria-label="獬豸助手提示" aria-atomic="true">
                    <h3>{currentAction?.title || '请稍候，正在整理下一步'}</h3>
                    <p className="guided-review-card__description">{currentAction?.description || '当前没有需要立即处理的事项。'}</p>
                  </div>
                </div>
              </div>
              {hasResponse && (
                <div className="guided-review-card__response" role="group" aria-label={responseLabel}>
                  <span className="guided-review-card__response-label">{responseLabel}</span>
                  {children}
                </div>
              )}
            </article>
            <div className="guided-review-tools" aria-label="其他审核操作">
              <span className="guided-review-tools__label">其他操作</span>
              <Button aria-expanded={openPanel === 'pending'} aria-controls="guided-review-pending-panel"
                onClick={() => togglePanel('pending')}>
                查看全部待处理事项
              </Button>
              <Button aria-expanded={openPanel === 'summary'} aria-controls="guided-review-summary-panel"
                onClick={() => togglePanel('summary')}>
                查看已整理信息
              </Button>
              <Button onClick={onOpenFullEditor}>完整审核编辑</Button>
              <Button type="link" onClick={onBackToWorkbench}>返回案件列表</Button>
            </div>
            {openPanel === 'pending' && (
              <div id="guided-review-pending-panel" className="guided-review-popover-panel" aria-label="全部待处理事项">
                {allActions.length ? allActions.map(action => (
                  <Button type="text" block key={action.id}
                    className={action.id === currentAction?.id ? 'guided-review-action--current' : ''}
                    onClick={() => onSelectAction(action.id)}>
                    <span>{action.title}</span>
                    <small>{action.description}</small>
                  </Button>
                )) : <p>当前没有待处理事项。</p>}
              </div>
            )}
            {openPanel === 'summary' && (
              <div id="guided-review-summary-panel" className="guided-review-popover-panel guided-review-summary" aria-label="已整理信息">
                {summary || <p>当前还没有可展示的整理摘要。</p>}
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}
