import React from 'react'
import EditableField from './EditableField'

interface ReviewFieldProps {
  targetId?: string
  label: string
  labelNote?: React.ReactNode
  type: 'text' | 'textarea'
  value: string
  onChange: (value: string) => void
  placeholder?: string
}

export function ReviewField({ targetId, label, labelNote, type, value, onChange, placeholder }: ReviewFieldProps) {
  return (
    <div id={targetId} className="review-field review-navigation-target" tabIndex={targetId ? -1 : undefined}>
      <div className="review-field__label-row">
        <div className="review-field__label">{label}</div>
        {labelNote && <span className="review-field__label-note">{labelNote}</span>}
      </div>
      <EditableField type={type} value={value} onChange={onChange} placeholder={placeholder} />
    </div>
  )
}
