import React from 'react'
import EditableField from './EditableField'

interface ReviewFieldProps {
  label: string
  type: 'text' | 'textarea'
  value: string
  onChange: (value: string) => void
  placeholder?: string
}

export function ReviewField({ label, type, value, onChange, placeholder }: ReviewFieldProps) {
  return (
    <div className="review-field">
      <div className="review-field__label">{label}</div>
      <EditableField type={type} value={value} onChange={onChange} placeholder={placeholder} />
    </div>
  )
}
