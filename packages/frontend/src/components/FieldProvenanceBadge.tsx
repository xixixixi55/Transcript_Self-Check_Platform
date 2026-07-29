// Layer 11: FE_Components — field source and pending state shown without exporting color to Word.
import React from 'react'
import { Space, Tag } from 'antd'
import type { FieldState } from '@biji/shared/types'
import { getFieldConfirmationMessage, getFieldSourceLabel } from '@biji/shared/utils'

const SOURCE_COLORS = { report: undefined, user: 'blue', system_default: 'default' } as const

export function FieldProvenanceBadge({ state }: { state?: FieldState }) {
  if (!state) return null
  const confirmationMessage = getFieldConfirmationMessage(state)
  return (
    <Space size={4} className="field-provenance-badge">
      <Tag color={SOURCE_COLORS[state.source]}>{getFieldSourceLabel(state.source)}</Tag>
      {confirmationMessage && <Tag color="orange">{confirmationMessage}</Tag>}
    </Space>
  )
}
