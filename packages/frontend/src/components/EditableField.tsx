// Layer 11: FE_Components — click-to-edit 通用字段组件
// REQ-019: 文本展示 → 点击 → 编辑 → 失焦保存 / Escape 取消
import React, { useState, useRef, useEffect } from 'react'
import { Input, Typography } from 'antd'
import { EditOutlined } from '@ant-design/icons'
import { HardwareDeviceSelect } from './HardwareDeviceSelect'

const { Text } = Typography
const { TextArea } = Input

export type EditableFieldType = 'text' | 'textarea' | 'select'

interface EditableFieldProps {
  type: EditableFieldType
  value: string
  onChange: (value: string) => void
  /** select 模式的选项 */
  options?: { label: string; value: string }[]
  placeholder?: string
}

export default function EditableField({
  type, value, onChange, options, placeholder,
}: EditableFieldProps) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value)
  const inputRef = useRef<HTMLInputElement | HTMLTextAreaElement>(null)

  // 同步外部 value 变化到 draft（非编辑态时）
  useEffect(() => {
    if (!editing) setDraft(value)
  }, [value, editing])

  const enterEdit = () => {
    setDraft(value)
    setEditing(true)
    // 下一帧聚焦
    setTimeout(() => {
      if (inputRef.current?.focus) inputRef.current.focus()
    }, 0)
  }

  const save = () => {
    setEditing(false)
    if (draft !== value) onChange(draft)
  }

  const cancel = () => {
    setEditing(false)
    setDraft(value)
  }

  const handleDisplayKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      enterEdit()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && type !== 'textarea') save()
    if (e.key === 'Escape') cancel()
  }

  if (!editing) {
    const display = value || placeholder || '点击编辑'
    const isEmpty = !value
    return (
      <Text
        className={`review-editable-display ${isEmpty ? 'review-editable-display--empty' : ''}`}
        onClick={enterEdit}
        onKeyDown={handleDisplayKeyDown}
        tabIndex={0}
        role="button"
        aria-label={`${display}，按 Enter 编辑`}
      >
        {display} <EditOutlined style={{ fontSize: 12, marginLeft: 4, opacity: 0.4 }} />
      </Text>
    )
  }

  if (type === 'select') {
    return (
      <HardwareDeviceSelect
        value={draft || undefined}
        onChange={(val) => { setDraft(val); onChange(val); setEditing(false) }}
        onBlur={save}
        style={{ width: '100%' }}
        options={options || []}
        placeholder={placeholder}
        open
        autoFocus
      />
    )
  }

  if (type === 'textarea') {
    return (
      <TextArea
        ref={inputRef as any}
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onBlur={save}
        onKeyDown={e => { if (e.key === 'Escape') cancel() }}
        rows={3}
        style={{ width: '100%' }}
      />
    )
  }

  return (
    <Input
      ref={inputRef as any}
      value={draft}
      onChange={e => setDraft(e.target.value)}
      onBlur={save}
      onKeyDown={handleKeyDown}
      onPressEnter={save}
      style={{ width: '100%' }}
    />
  )
}
