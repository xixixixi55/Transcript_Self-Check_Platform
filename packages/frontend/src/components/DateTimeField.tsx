import React, { useEffect, useState } from 'react'
import { Input, Space } from 'antd'
import {
  fromDateInputValue,
  fromDateTimeRangeInputValues,
  isCompleteDateTimeRange,
  toDateInputValue,
  toDateTimeRangeInputValues,
} from '@biji/shared/utils'

export type DateTimeFieldPrecision = 'date' | 'minute-range'

interface DateTimeFieldProps {
  label?: string
  precision: DateTimeFieldPrecision
  value: string
  onChange: (value: string) => void
}

function DateTimeField({ label, precision, value, onChange }: DateTimeFieldProps) {
  const [rangeValues, setRangeValues] = useState(() => toDateTimeRangeInputValues(value))

  useEffect(() => {
    setRangeValues(toDateTimeRangeInputValues(value))
  }, [value])

  const handleDateChange = (nextValue: string) => {
    onChange(fromDateInputValue(nextValue))
  }

  const handleRangeChange = (side: 'start' | 'end', nextValue: string) => {
    const nextRange = { ...rangeValues, [side]: nextValue }
    setRangeValues(nextRange)
    if (!nextRange.start && !nextRange.end) {
      onChange('')
      return
    }
    if (isCompleteDateTimeRange(nextRange.start, nextRange.end)) {
      onChange(fromDateTimeRangeInputValues(nextRange.start, nextRange.end))
    }
  }

  return (
    <div style={{ marginTop: 4 }}>
      {label && <div style={{ fontWeight: 600, marginBottom: 4, marginTop: 12 }}>{label}</div>}
      {precision === 'date' ? (
        <Input
          aria-label={label || '日期'}
          type="date"
          value={toDateInputValue(value)}
          onChange={event => handleDateChange(event.target.value)}
          style={{ width: '100%' }}
        />
      ) : (
        <Space wrap>
          <Input
            aria-label={`${label || '时间范围'}开始`}
            type="datetime-local"
            step={60}
            value={rangeValues.start}
            onChange={event => handleRangeChange('start', event.target.value)}
          />
          <span>至</span>
          <Input
            aria-label={`${label || '时间范围'}结束`}
            type="datetime-local"
            step={60}
            value={rangeValues.end}
            onChange={event => handleRangeChange('end', event.target.value)}
          />
        </Space>
      )}
    </div>
  )
}

export { DateTimeField }
