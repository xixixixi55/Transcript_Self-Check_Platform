import React, { forwardRef } from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import EditableField from './EditableField'

vi.mock('antd', () => {
  type MockInputProps = React.InputHTMLAttributes<HTMLInputElement> & { onPressEnter?: () => void }
  const Input = forwardRef<HTMLInputElement, MockInputProps>(
    ({ onPressEnter: _onPressEnter, ...props }, ref) => <input ref={ref} {...props} />,
  )
  const TextArea = forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
    (props, ref) => <textarea ref={ref} {...props} />,
  )

  return {
    Input: Object.assign(Input, { TextArea }),
    Select: ({ value, onChange, onBlur, options = [], ...props }: any) => (
      <select value={value ?? ''} onChange={(event: React.ChangeEvent<HTMLSelectElement>) => onChange(event.target.value)} onBlur={onBlur} {...props}>
        {options.map((option: { label: string; value: string }) => (
          <option key={option.value} value={option.value}>{option.label}</option>
        ))}
      </select>
    ),
    Typography: {
      Text: ({ children, ...props }: React.HTMLAttributes<HTMLSpanElement>) => <span {...props}>{children}</span>,
    },
  }
})

vi.mock('@ant-design/icons', () => ({
  EditOutlined: () => <span aria-label="编辑" />,
}))

describe('EditableField', () => {
  it('点击文本后可在失焦时保存修改', () => {
    const onChange = vi.fn()
    const view = render(<EditableField type="text" value="原始值" onChange={onChange} />)

    fireEvent.click(screen.getByText('原始值'))
    const input = screen.getByDisplayValue('原始值')
    fireEvent.change(input, { target: { value: '新值' } })
    fireEvent.blur(input)

    expect(onChange).toHaveBeenCalledWith('新值')
    view.rerender(<EditableField type="text" value="新值" onChange={onChange} />)
    expect(screen.getByText('新值')).toBeTruthy()
  })

  it('按 Escape 取消修改并恢复展示态', () => {
    const onChange = vi.fn()
    render(<EditableField type="text" value="原始值" onChange={onChange} />)

    fireEvent.click(screen.getByText('原始值'))
    const input = screen.getByDisplayValue('原始值')
    fireEvent.change(input, { target: { value: '草稿' } })
    fireEvent.keyDown(input, { key: 'Escape' })

    expect(onChange).not.toHaveBeenCalled()
    expect(screen.getByText('原始值')).toBeTruthy()
  })

  it('根据类型渲染 textarea 和 select，并提交选择值', () => {
    const onChange = vi.fn()
    const textareaView = render(<EditableField type="textarea" value="多行" onChange={onChange} />)

    fireEvent.click(screen.getByText('多行'))
    expect(screen.getByDisplayValue('多行').tagName).toBe('TEXTAREA')

    textareaView.unmount()
    render(<EditableField type="select" value="a" onChange={onChange} options={[
      { label: 'A', value: 'a' }, { label: 'B', value: 'b' },
    ]} />)
    fireEvent.click(screen.getByText('a'))
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'b' } })

    expect(onChange).toHaveBeenCalledWith('b')
  })

  it('为空值显示点击编辑占位文字', () => {
    render(<EditableField type="text" value="" onChange={vi.fn()} />)
    expect(screen.getByText('点击编辑')).toBeTruthy()
  })
})
