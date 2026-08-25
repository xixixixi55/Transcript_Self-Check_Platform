import { SafetyCertificateOutlined } from '@ant-design/icons'
import { Badge, Button } from 'antd'
import { useState } from 'react'
import type { GuidedReviewAction, GuidedReviewHistoryItem } from '../hooks/useGuidedReviewCards'
import { GuidedReviewHistory } from './GuidedReviewHistory'

interface Props {
  history: GuidedReviewHistoryItem[]
  currentAction: GuidedReviewAction | null
  allActions: GuidedReviewAction[]
  onSelectAction: (actionId: string) => void
  summary: React.ReactNode
  onOpenFullEditor: () => void
  onBackToWorkbench: () => void
  children: React.ReactNode
}

export function GuidedReviewView({
  history, currentAction, allActions, onSelectAction, summary,
  onOpenFullEditor, onBackToWorkbench, children,
}: Props) {
  const [openPanel, setOpenPanel] = useState<'pending' | 'summary' | null>(null)
  const togglePanel = (panel: 'pending' | 'summary') => {
    setOpenPanel(current => current === panel ? null : panel)
  }

  return (
    <div className="guided-review-view">
      <GuidedReviewHistory items={history} />
      <section className="guided-review-conversation" role="region"
        aria-labelledby="guided-review-conversation-title">
        <div className="guided-review-conversation__assistant" aria-hidden>
          <SafetyCertificateOutlined />
        </div>
        <div className="guided-review-conversation__body">
          <div className="guided-review-conversation__heading">
            <div>
              <h2 id="guided-review-conversation-title">当前对话</h2>
              <p>獬豸助手会优先推荐当前可办理事项，所有操作仍写入同一案件草稿。</p>
            </div>
            <Badge count={allActions.filter(action => action.kind === 'pending_item').length}
              showZero overflowCount={99} title="需要用户处理的事项数" />
          </div>
          <article className="guided-review-card" aria-live="polite">
            <h3>{currentAction?.title || '等待下一步办理'}</h3>
            <p className="guided-review-card__description">{currentAction?.description || '当前没有需要立即处理的事项。'}</p>
            {children}
          </article>
          <div className="guided-review-tools" aria-label="审核导航">
            <Button aria-expanded={openPanel === 'pending'} onClick={() => togglePanel('pending')}>
              查看全部待处理事项
            </Button>
            <Button aria-expanded={openPanel === 'summary'} onClick={() => togglePanel('summary')}>
              查看已整理信息
            </Button>
            <Button onClick={onOpenFullEditor}>完整审核编辑</Button>
            <Button type="link" onClick={onBackToWorkbench}>返回案件列表</Button>
          </div>
          {openPanel === 'pending' && (
            <div className="guided-review-popover-panel" aria-label="全部待处理事项">
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
            <div className="guided-review-popover-panel guided-review-summary" aria-label="已整理信息">
              {summary || <p>当前还没有可展示的整理摘要。</p>}
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
