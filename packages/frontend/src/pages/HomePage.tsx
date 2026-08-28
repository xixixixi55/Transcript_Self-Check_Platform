// 第 12 层：FE_Pages — 平台成果总览

import { Typography } from 'antd'
import {
  ApartmentOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons'
import '../homePage.css'

const { Paragraph, Text, Title } = Typography
const numberFormatter = new Intl.NumberFormat('zh-CN')

interface HomeAchievementBase {
  key: string
  icon: typeof FileTextOutlined
  title: string
}

export type HomeAchievementState =
  | { state: 'pending' }
  | { state: 'loading' }
  | { state: 'unavailable' }
  | { state: 'ready'; total: number; recent14d: number; updatedAt: string }

export type HomeAchievementItem = HomeAchievementBase & (
  | {
    status: 'available'
    metricLabel: string
    unit: string
    achievement: HomeAchievementState
  }
  | { status: 'comingSoon' }
)

export const platformHomeAchievements = [
  {
    key: 'electronic-inspection',
    icon: FileTextOutlined,
    title: '电子数据检查笔录',
    status: 'available',
    metricLabel: '累计成功处理案件',
    unit: '件',
    achievement: { state: 'pending' },
  },
  { key: 'professional-report', icon: FileSearchOutlined, title: '专业化勘查报告', status: 'comingSoon' },
  { key: 'digital-forensic', icon: ApartmentOutlined, title: '电子数据鉴定文书', status: 'comingSoon' },
  { key: 'scene-triple', icon: FileTextOutlined, title: '传统现场三录', status: 'comingSoon' },
  { key: 'scene-inspection', icon: FileSearchOutlined, title: '传统现场检查笔录', status: 'comingSoon' },
  { key: 'forensic-medical', icon: SafetyCertificateOutlined, title: '法医鉴定文书自检', status: 'comingSoon' },
] satisfies readonly HomeAchievementItem[]

interface HomePageContentProps {
  items?: readonly HomeAchievementItem[]
}

function achievementPresentation(achievement: HomeAchievementState) {
  if (achievement.state === 'ready') {
    const recentPrefix = achievement.recent14d > 0 ? '+' : ''
    return {
      total: numberFormatter.format(achievement.total),
      recent: `${recentPrefix}${numberFormatter.format(achievement.recent14d)}`,
      updatedAt: achievement.updatedAt,
      status: '数据已更新',
      note: '仅展示聚合统计，不包含案件或人员明细。',
    }
  }
  if (achievement.state === 'loading') {
    return { total: '—', recent: '—', updatedAt: '—', status: '正在加载', note: '正在读取已确认口径的聚合统计。' }
  }
  if (achievement.state === 'unavailable') {
    return { total: '—', recent: '—', updatedAt: '—', status: '统计暂时不可用', note: '数据恢复后将在当前区域继续展示。' }
  }
  return { total: '—', recent: '—', updatedAt: '—', status: '数据待接入', note: '统计口径确认并接入后，此处将展示真实成果。' }
}

function AchievementCard({ item }: { item: Extract<HomeAchievementItem, { status: 'available' }> }) {
  const { icon: Icon, title, metricLabel, unit, achievement } = item
  const presentation = achievementPresentation(achievement)

  return (
    <article className="platform-home__achievement-card" aria-label={`${title}成果`}
      aria-busy={achievement.state === 'loading'}>
      <div className="platform-home__achievement-summary">
        <div className="platform-home__achievement-title">
          <span className="platform-home__achievement-icon" aria-hidden="true"><Icon /></span>
          <Title level={3}>{title}</Title>
        </div>
        <div className="platform-home__primary-metric">
          <Text>{metricLabel}</Text>
          <div className="platform-home__primary-value">
            <strong>{presentation.total}</strong><span>{unit}</span>
          </div>
        </div>
      </div>
      <div className="platform-home__achievement-detail">
        <span className={`platform-home__data-status platform-home__data-status--${achievement.state}`}>
          {presentation.status}
        </span>
        <dl className="platform-home__metric-list">
          <div>
            <dt>近两周新增</dt>
            <dd>{presentation.recent}<small>{unit}</small></dd>
          </div>
          <div>
            <dt>数据更新时间</dt>
            <dd>{presentation.updatedAt}</dd>
          </div>
        </dl>
        <Paragraph className="platform-home__data-note">{presentation.note}</Paragraph>
      </div>
    </article>
  )
}

export function HomePageContent({ items = platformHomeAchievements }: HomePageContentProps) {
  const availableItems = items.filter(
    (item): item is Extract<HomeAchievementItem, { status: 'available' }> => item.status === 'available',
  )
  const columnCount = Math.min(Math.max(availableItems.length, 1), 3)

  return (
    <div className="platform-home">
      <div className="platform-page platform-home__inner">
        <header className="platform-home__heading">
          <Title level={1}>工作成果</Title>
          <Paragraph>汇总展示各项已开放能力的累计成果与近两周变化。</Paragraph>
        </header>

        <section className="platform-home__results" aria-labelledby="platform-achievements-title">
          <div className="platform-home__results-heading">
            <Title level={2} id="platform-achievements-title">已开放功能</Title>
            <Text>{availableItems.length} 项能力</Text>
          </div>
          <div className={`platform-home__achievement-grid platform-home__achievement-grid--count-${columnCount}`}
            data-available-count={availableItems.length}>
            {availableItems.map(item => <AchievementCard key={item.key} item={item} />)}
          </div>
        </section>
      </div>
    </div>
  )
}

export default function HomePage() {
  return <HomePageContent />
}
