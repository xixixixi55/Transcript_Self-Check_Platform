// Layer 11: FE_Components — 检查过程编辑器
// REQ-017: 展示 4 个步骤，步骤号固定，内容可编辑
import React from 'react'
import { Typography, Space } from 'antd'
import EditableField from './EditableField'
import type { ProcessStep } from '@biji/shared/types'

const { Text } = Typography

interface Props {
  steps: ProcessStep[]
  onChange: (steps: ProcessStep[]) => void
}

export default function ProcessStepsEditor({ steps, onChange }: Props) {
  const updateStep = (idx: number, content: string) => {
    onChange(steps.map((s, i) => i === idx ? { ...s, content } : s))
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={8}>
      {steps.map((step, idx) => (
        <div key={step.step_number || idx} style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
          <Text strong style={{ minWidth: 28, lineHeight: '32px' }}>
            {step.step_number}、
          </Text>
          <div style={{ flex: 1 }}>
            <EditableField
              type="textarea"
              value={step.content}
              onChange={(val) => updateStep(idx, val)}
            />
          </div>
        </div>
      ))}
      {steps.length === 0 && <Text type="secondary">暂无检查过程步骤</Text>}
    </Space>
  )
}
