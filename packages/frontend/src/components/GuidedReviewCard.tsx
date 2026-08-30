import { CheckCircleOutlined, EditOutlined, FileAddOutlined, FileSearchOutlined, SortAscendingOutlined } from '@ant-design/icons'
import { Alert, Button, Input, message, Space, Tooltip } from 'antd'
import { useEffect, useState } from 'react'
import type { EvidenceItem, FieldState, InspectionReport } from '@biji/shared/types'
import type { GuidedReviewAction } from '../hooks/useGuidedReviewCards'
import { REVIEW_TARGET_IDS } from '../hooks/useReviewChecklist'
import { DateTimeField } from './DateTimeField'
import { DocumentNumberEditor } from './DocumentNumberEditor'
import EvidenceEditor from './EvidenceEditor'
import { normalizeEntrustPersons } from './ReviewIntroductionSection'

interface Props {
  action: GuidedReviewAction
  report: InspectionReport
  updateReport: (path: string, value: unknown) => void
  readOnly: boolean
  specialContent?: React.ReactNode
  fieldStates?: Record<string, FieldState>
  onEvidenceCompletenessChange?: (confirmed: boolean) => void
  onOpenFullEditor?: (targetId?: string) => void
}

interface TextField {
  path: string
  value: string
  multiline?: boolean
  transform?: (value: string) => unknown
}

interface EvidenceBatchPreview {
  deviceName: string
  materialType: 'phone' | 'tablet'
  unextractableReason: string
  evidenceNumber: string
}

interface EvidenceBatchResult {
  preview: EvidenceBatchPreview[]
  errors: string[]
}

interface NaturalEvidenceOrder<T> {
  items: T[]
  applied: boolean
}

function evidenceNumberKey(value: string): number[] | null {
  const groups = value.match(/\d+/g)
  if (!groups) return null
  const numbers = groups.map(Number)
  return numbers.every(Number.isSafeInteger) ? numbers : null
}

function naturalEvidenceOrder<T>(items: T[], getNumber: (item: T) => string): NaturalEvidenceOrder<T> {
  const keyed = items.map(item => ({ item, key: evidenceNumberKey(getNumber(item)) }))
  if (keyed.some(candidate => candidate.key === null)) return { items, applied: false }
  const serializedKeys = keyed.map(candidate => JSON.stringify(candidate.key))
  if (new Set(serializedKeys).size !== serializedKeys.length) return { items, applied: false }
  return {
    applied: true,
    items: [...keyed].sort((left, right) => {
      const leftKey = left.key as number[]
      const rightKey = right.key as number[]
      const length = Math.max(leftKey.length, rightKey.length)
      for (let index = 0; index < length; index += 1) {
        if (index >= leftKey.length) return -1
        if (index >= rightKey.length) return 1
        if (leftKey[index] !== rightKey[index]) return leftKey[index] - rightKey[index]
      }
      return 0
    }).map(candidate => candidate.item),
  }
}

function formatEvidencePreview(candidate: EvidenceBatchPreview): string {
  const typeLabel = candidate.materialType === 'phone' ? '手机' : '平板'
  return `${candidate.deviceName}${typeLabel}一部（${candidate.unextractableReason}）${candidate.evidenceNumber}`
}

function parseEvidenceBatch(value: string, existingItems: EvidenceItem[]): EvidenceBatchResult {
  const existingNumbers = new Set(existingItems
    .map(item => String(item.evidence_number || '').trim().toLocaleLowerCase()).filter(Boolean))
  const batchNumbers = new Set<string>()
  const preview: EvidenceBatchPreview[] = []
  const errors: string[] = []

  value.split(/\r?\n/).forEach((rawLine, index) => {
    const line = rawLine.trim()
    if (!line) return
    const match = line.match(/^(.+?)(手机|平板)\s*一部\s*（([^（）]+)）\s*([^\s（）]+)$/)
    if (!match) {
      errors.push(`第 ${index + 1} 行：格式不正确，请使用中文全角括号并把检材编号放在行末。`)
      return
    }
    const [, rawDeviceName, typeLabel, rawReason, rawEvidenceNumber] = match
    const deviceName = rawDeviceName.trim()
    const unextractableReason = rawReason.trim()
    const evidenceNumber = rawEvidenceNumber.trim()
    const normalizedNumber = evidenceNumber.toLocaleLowerCase()
    if (existingNumbers.has(normalizedNumber)) {
      errors.push(`第 ${index + 1} 行：检材编号 ${evidenceNumber} 已存在。`)
      return
    }
    if (batchNumbers.has(normalizedNumber)) {
      errors.push(`第 ${index + 1} 行：检材编号 ${evidenceNumber} 在本次输入中重复。`)
      return
    }
    batchNumbers.add(normalizedNumber)
    preview.push({
      deviceName,
      materialType: typeLabel === '手机' ? 'phone' : 'tablet',
      unextractableReason,
      evidenceNumber,
    })
  })

  if (!preview.length && !errors.length) errors.push('请输入至少一项检材。')
  return { preview, errors }
}

function QuickEvidenceBatchAdder({ items, onChange, onConfirmComplete }: {
  items: EvidenceItem[]
  onChange: (items: EvidenceItem[]) => void
  onConfirmComplete?: () => void
}) {
  const [value, setValue] = useState('')
  const [result, setResult] = useState<EvidenceBatchResult | null>(null)
  const [sortRequested, setSortRequested] = useState(false)
  const [sortFeedback, setSortFeedback] = useState<{ message: string } | null>(null)
  const [messageApi, messageContextHolder] = message.useMessage({ maxCount: 2, top: 24 })
  const showSuccess = (content: string) => messageApi.open({
    key: 'quick-evidence-success',
    type: 'success',
    content,
    duration: 2.5,
  })
  const parse = () => {
    const parsed = parseEvidenceBatch(value, items)
    setResult(parsed)
    if (parsed.errors.length) setSortRequested(false)
    else showSuccess(`已识别 ${parsed.preview.length} 项检材，请确认后添加。`)
    setSortFeedback(null)
  }
  const sort = () => {
    if (!value.trim()) {
      const ordered = naturalEvidenceOrder(items, item => item.evidence_number)
      if (!ordered.applied) {
        setSortFeedback({ message: '当前检材编号无法安全排序，已保持原顺序。' })
        return
      }
      onChange(ordered.items)
      setSortFeedback(null)
      showSuccess('已按检材编号自然升序排列。')
      return
    }

    const parsed = parseEvidenceBatch(value, items)
    setResult(parsed)
    if (parsed.errors.length) {
      setSortRequested(false)
      setSortFeedback(null)
      return
    }
    const combined = [
      ...items.map(item => ({ evidenceNumber: item.evidence_number, preview: null as EvidenceBatchPreview | null })),
      ...parsed.preview.map(preview => ({ evidenceNumber: preview.evidenceNumber, preview })),
    ]
    const ordered = naturalEvidenceOrder(combined, item => item.evidenceNumber)
    if (!ordered.applied) {
      setSortRequested(false)
      setSortFeedback({ message: '当前检材编号无法安全排序，已保持原顺序。' })
      return
    }
    const orderedPreview = ordered.items.flatMap(item => item.preview ? [item.preview] : [])
    setResult({ preview: orderedPreview, errors: [] })
    setValue(orderedPreview.map(formatEvidencePreview).join('\n'))
    setSortRequested(true)
    setSortFeedback(null)
    showSuccess('已按检材编号自然升序排列。')
  }
  const confirm = () => {
    if (!result || result.errors.length || !result.preview.length) return
    const createdAt = Date.now()
    const additions = result.preview.map((candidate, index): EvidenceItem => {
      const evidenceId = `local-evidence-${createdAt}-${items.length + index + 1}`
      return {
        id: evidenceId,
        evidence_id: evidenceId,
        device_type: '',
        device_name: candidate.deviceName,
        model: candidate.deviceName,
        imei1: '',
        imei2: '',
        serial_number: '',
        extractable: false,
        unextractable_reason: candidate.unextractableReason,
        evidence_number: candidate.evidenceNumber,
        material_type: candidate.materialType,
        material_type_status: 'confirmed_by_user',
        material_type_source: 'user',
      }
    })
    const nextItems = [...items, ...additions]
    onChange(sortRequested
      ? naturalEvidenceOrder(nextItems, item => item.evidence_number).items
      : nextItems)
    setValue('')
    setResult(null)
    setSortRequested(false)
    setSortFeedback(null)
    showSuccess(`已添加 ${additions.length} 项检材。`)
  }

  return (
    <>
      {messageContextHolder}
      <div className="guided-review-card__quick-evidence">
        <div className="guided-review-card__quick-evidence-intro">
          <span className="guided-review-card__quick-evidence-icon" aria-hidden="true">
            <FileAddOutlined />
          </span>
          <div className="guided-review-card__quick-evidence-copy">
            <h4>快捷批量添加检材</h4>
            <div id="quick-evidence-format-help">
              <p>每行一项：设备名称＋手机/平板一部＋（原因）＋编号；全角括号，编号置于行末。</p>
            </div>
          </div>
        </div>
        <Space direction="vertical" size="small" style={{ width: '100%', marginTop: 12 }}>
          <Input.TextArea aria-label="快捷批量添加检材" aria-describedby="quick-evidence-format-help" value={value}
            placeholder={'iPhone 6手机一部（因设备损坏无法提取）JC2026089601\niPad平板一部（因无法开机无法提取）JC2026089602'}
            autoSize={{ minRows: 4, maxRows: 10 }} maxLength={5000}
            onChange={event => {
              setValue(event.target.value)
              setResult(null)
              setSortRequested(false)
              setSortFeedback(null)
            }} />
          <div className="guided-review-card__quick-evidence-actions" role="group" aria-label="快捷检材操作">
            <Tooltip title="解析并预览">
              <Button shape="circle" size="large" className="guided-review-icon-action"
                icon={<FileSearchOutlined />} aria-label="解析并预览"
                onClick={parse} disabled={!value.trim()} />
            </Tooltip>
            <Tooltip title="一键排序">
              <Button shape="circle" size="large" className="guided-review-icon-action"
                icon={<SortAscendingOutlined />} aria-label="一键排序"
                onClick={sort} disabled={!value.trim() && items.length < 2} />
            </Tooltip>
            <Tooltip title="完成检材补充并确认完整">
              <Button type="primary" shape="circle" size="large" className="guided-review-icon-action"
                icon={<CheckCircleOutlined />}
                aria-label="完成检材补充并确认完整" onClick={onConfirmComplete} />
            </Tooltip>
          </div>
          {sortFeedback ? <Alert type="warning" showIcon message={sortFeedback.message} /> : null}
          {result?.errors.length ? (
            <Alert type="error" showIcon message="无法添加，请修正以下内容" description={<ul>
              {result.errors.map(error => <li key={error}>{error}</li>)}
            </ul>} />
          ) : null}
          {result && !result.errors.length ? <>
            <ul className="guided-review-card__quick-evidence-preview">
              {result.preview.map(candidate => <li key={candidate.evidenceNumber}>
                {candidate.deviceName} · {candidate.materialType === 'phone' ? '手机' : '平板'} ·
                {' '}{candidate.evidenceNumber} · {candidate.unextractableReason}
              </li>)}
            </ul>
            <Tooltip title={`确认添加 ${result.preview.length} 项检材`}>
              <Button type="primary" shape="circle" size="large"
                className="guided-review-icon-action guided-review-card__quick-evidence-confirm"
                icon={<CheckCircleOutlined />} aria-label={`确认添加 ${result.preview.length} 项检材`} onClick={confirm} />
            </Tooltip>
          </> : null}
        </Space>
      </div>
    </>
  )
}

function resultField(report: InspectionReport, targetId: string): TextField | null {
  const keys = ['evidence_number', 'data_summary', 'rar_filename', 'md5_hash', 'file_size'] as const
  const key = keys.find(candidate => targetId === REVIEW_TARGET_IDS.result(candidate))
  return key ? {
    path: `inspection.result.${key}`,
    value: report.inspection.result[key],
    multiline: key === 'data_summary',
  } : null
}

function textField(report: InspectionReport, targetId: string): TextField | null {
  const introduction = report.introduction
  const inspection = report.inspection
  const primarySoftware = inspection.primary_software
  const fields: Record<string, TextField> = {
    [REVIEW_TARGET_IDS.documentNumber]: { path: 'document_number', value: report.document_number },
    [REVIEW_TARGET_IDS.entrustUnit]: { path: 'introduction.entrust_unit', value: introduction.entrust_unit },
    [REVIEW_TARGET_IDS.entrustPersons]: {
      path: 'introduction.entrust_persons', value: introduction.entrust_persons.join('、'),
      transform: normalizeEntrustPersons,
    },
    [REVIEW_TARGET_IDS.caseSummary]: { path: 'introduction.case_summary', value: introduction.case_summary, multiline: true },
    [REVIEW_TARGET_IDS.inspectionRequirement]: {
      path: 'introduction.inspection_requirement', value: introduction.inspection_requirement, multiline: true,
    },
    [REVIEW_TARGET_IDS.inspectionPlace]: { path: 'introduction.inspection_place', value: introduction.inspection_place },
    [REVIEW_TARGET_IDS.inspectionMethod]: { path: 'inspection.method', value: inspection.method, multiline: true },
    [REVIEW_TARGET_IDS.hardwareDevice]: { path: 'inspection.hardware_device', value: inspection.hardware_device },
    [REVIEW_TARGET_IDS.primarySoftwareName]: {
      path: 'inspection.primary_software.name', value: primarySoftware?.name || '',
    },
    [REVIEW_TARGET_IDS.primarySoftwareVersion]: {
      path: 'inspection.primary_software.version', value: primarySoftware?.version || '',
    },
    [REVIEW_TARGET_IDS.discNumber]: { path: 'attachments.disc_number', value: report.attachments.disc_number },
  }
  return fields[targetId] || resultField(report, targetId)
}

export function GuidedReviewCard({
  action, report, updateReport, readOnly, specialContent,
  fieldStates, onEvidenceCompletenessChange, onOpenFullEditor,
}: Props) {
  const [evidenceMode, setEvidenceMode] = useState<'closed' | 'choose' | 'batch' | 'manual'>('closed')
  useEffect(() => setEvidenceMode('closed'), [action.id])

  if (specialContent) return <div className="guided-review-card__control">{specialContent}</div>
  const pending = action.pendingItem
  if (!pending) return null
  const { targetId, fieldLabel } = pending

  if (targetId === REVIEW_TARGET_IDS.documentNumber && report.document_number_template) return (
    <fieldset disabled={readOnly} className="guided-review-card__fieldset">
      <DocumentNumberEditor template={report.document_number_template}
        documentNumber={report.document_number} onChange={value => updateReport('document_number', value)} />
    </fieldset>
  )
  if (targetId === REVIEW_TARGET_IDS.entrustTime) return (
    <fieldset disabled={readOnly} className="guided-review-card__fieldset">
      <DateTimeField label={fieldLabel} precision="date" value={report.introduction.entrust_time}
        onChange={value => updateReport('introduction.entrust_time', value)} />
    </fieldset>
  )
  if (targetId === REVIEW_TARGET_IDS.inspectionTimeRange) return (
    <fieldset disabled={readOnly} className="guided-review-card__fieldset">
      <DateTimeField label={fieldLabel} precision="minute-range" value={report.introduction.inspection_time_range}
        onChange={value => updateReport('introduction.inspection_time_range', value)} />
    </fieldset>
  )
  if (targetId === REVIEW_TARGET_IDS.burningDate) return (
    <fieldset disabled={readOnly} className="guided-review-card__fieldset">
      <DateTimeField label={fieldLabel} precision="date" value={report.attachments.burning_date || ''}
        onChange={value => updateReport('attachments.burning_date', value)} />
    </fieldset>
  )
  if (targetId === REVIEW_TARGET_IDS.evidenceCompleteness && evidenceMode === 'choose') return (
    <div className="guided-review-card__evidence-paths" role="group" aria-label="选择检材补充方式">
      <p>选择一种补充方式；页面一次只展开当前需要的工具。</p>
      <Space wrap size="small" className="guided-review-card__evidence-icon-actions">
        <Tooltip title="快捷批量补充">
          <Button type="primary" shape="circle" size="large" className="guided-review-icon-action"
            icon={<FileSearchOutlined />} disabled={readOnly}
            aria-label="快捷批量补充检材" onClick={() => setEvidenceMode('batch')} />
        </Tooltip>
        <Tooltip title="逐项编辑">
          <Button shape="circle" size="large" className="guided-review-icon-action"
            icon={<FileAddOutlined />} disabled={readOnly}
            aria-label="逐项编辑检材" onClick={() => setEvidenceMode('manual')} />
        </Tooltip>
      </Space>
    </div>
  )
  if (targetId === REVIEW_TARGET_IDS.evidenceCompleteness && evidenceMode === 'batch') return (
    <div className="guided-review-card__evidence-editor">
      <fieldset disabled={readOnly} className="guided-review-card__fieldset">
        <QuickEvidenceBatchAdder items={report.introduction.evidence_list || []}
          onChange={items => {
            updateReport('introduction.evidence_list', items)
            onEvidenceCompletenessChange?.(false)
          }} onConfirmComplete={() => onEvidenceCompletenessChange?.(true)} />
        <div className="guided-review-card__evidence-icon-actions guided-review-card__evidence-icon-actions--end">
          <Tooltip title="改用逐项编辑">
            <Button shape="circle" size="large" className="guided-review-icon-action"
              icon={<FileAddOutlined />} aria-label="改用逐项编辑"
              onClick={() => setEvidenceMode('manual')} />
          </Tooltip>
        </div>
      </fieldset>
    </div>
  )
  if (targetId === REVIEW_TARGET_IDS.evidenceCompleteness && evidenceMode === 'manual') return (
    <div className="guided-review-card__evidence-editor">
      <fieldset disabled={readOnly} className="guided-review-card__fieldset">
        <EvidenceEditor items={report.introduction.evidence_list || []} fieldStates={fieldStates} compactActions
          onChange={items => {
            updateReport('introduction.evidence_list', items)
            onEvidenceCompletenessChange?.(false)
          }} />
        <div className="guided-review-card__evidence-icon-actions guided-review-card__evidence-icon-actions--end">
          <Tooltip title="完成补充">
            <Button type="primary" shape="circle" size="large" className="guided-review-icon-action"
              icon={<CheckCircleOutlined />}
              aria-label="完成检材补充并确认完整" onClick={() => onEvidenceCompletenessChange?.(true)} />
          </Tooltip>
          <Tooltip title="改用快捷批量补充">
            <Button shape="circle" size="large" className="guided-review-icon-action"
              icon={<FileSearchOutlined />} aria-label="改用快捷批量补充"
              onClick={() => setEvidenceMode('batch')} />
          </Tooltip>
        </div>
      </fieldset>
    </div>
  )
  if (targetId === REVIEW_TARGET_IDS.evidenceCompleteness) return (
    <Space role="group" aria-label="检材完整性选择" size="middle" className="guided-review-card__choice-actions">
      <Tooltip title="完整">
        <Button type="primary" shape="circle" size="large" className="guided-review-icon-action" disabled={readOnly}
          icon={<CheckCircleOutlined />} aria-label="确认检材信息完整"
          onClick={() => onEvidenceCompletenessChange?.(true)} />
      </Tooltip>
      <Tooltip title="不完整，手工添加检材">
        <Button shape="circle" size="large" className="guided-review-icon-action" disabled={readOnly}
          icon={<FileAddOutlined />} aria-label="检材信息不完整，手工添加检材"
          onClick={() => setEvidenceMode('choose')} />
      </Tooltip>
    </Space>
  )

  const field = textField(report, targetId)
  if (field) {
    const change = (value: string) => updateReport(field.path, field.transform ? field.transform(value) : value)
    return (
      <label className="guided-review-card__field">
        <span>{fieldLabel}</span>
        {field.multiline
          ? <Input.TextArea aria-label={fieldLabel} value={field.value} disabled={readOnly}
              autoSize={{ minRows: 2, maxRows: 5 }} onChange={event => change(event.target.value)} />
          : <Input aria-label={fieldLabel} value={field.value} disabled={readOnly}
              onChange={event => change(event.target.value)} />}
      </label>
    )
  }

  return (
    <div className="guided-review-card__fallback">
      <p>此事项使用完整审核编辑中的现有结构化控件办理。</p>
      <Tooltip title="在完整审核编辑中处理此项">
        <Button type="primary" shape="circle" size="large" className="guided-review-icon-action"
          icon={<EditOutlined />} aria-label="在完整审核编辑中处理此项"
          onClick={() => onOpenFullEditor?.(targetId)} />
      </Tooltip>
    </div>
  )
}
