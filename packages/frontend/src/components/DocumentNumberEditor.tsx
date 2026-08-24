// Layer 11: FE_Components — case-scoped sequence input for a snapshotted document-number format.
import { useEffect, useState } from 'react'
import { Input } from 'antd'
import type { DocumentNumberTemplate } from '@biji/shared/types'

interface Props {
  targetId?: string
  template: DocumentNumberTemplate
  documentNumber: string
  onChange: (documentNumber: string) => void
}

export function documentNumberSequence(
  documentNumber: string,
  template: DocumentNumberTemplate,
): string | null {
  const { prefix, suffix } = template
  if (!prefix && !suffix) return null
  if (!documentNumber) return ''
  if (!documentNumber.startsWith(prefix) || !documentNumber.endsWith(suffix)) return null
  const end = suffix ? documentNumber.length - suffix.length : documentNumber.length
  const sequence = documentNumber.slice(prefix.length, end)
  return /^\d*$/.test(sequence) ? sequence : null
}

export function DocumentNumberEditor({
  targetId, template, documentNumber, onChange,
}: Props) {
  const sequence = documentNumberSequence(documentNumber, template) ?? ''
  const [draft, setDraft] = useState(sequence)
  const invalid = !/^\d*$/.test(draft)

  useEffect(() => { setDraft(sequence) }, [sequence])

  const handleChange = (value: string) => {
    setDraft(value)
    if (/^\d*$/.test(value)) {
      onChange(value ? `${template.prefix}${value}${template.suffix}` : '')
    }
  }

  return (
    <div id={targetId} className="review-field review-navigation-target"
      tabIndex={targetId ? -1 : undefined}>
      <div className="review-field__label">文号编号</div>
      <div className="document-number-editor">
        {template.prefix && <span className="document-number-editor__affix">{template.prefix}</span>}
        <Input aria-label="文号编号" aria-invalid={invalid} inputMode="numeric"
          autoComplete="off" maxLength={30} value={draft}
          placeholder="填写编号" onChange={event => handleChange(event.target.value)} />
        {template.suffix && <span className="document-number-editor__affix">{template.suffix}</span>}
      </div>
      {invalid && <div className="document-number-editor__error" role="alert">编号只能填写数字。</div>}
    </div>
  )
}
