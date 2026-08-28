// 第 10 层：FE_Hooks — useEditableState 测试
import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useEditableState } from './useEditableState'

describe('useEditableState', () => {
  it('初始状态无编辑字段', () => {
    const { result } = renderHook(() => useEditableState())
    expect(result.current.editingField).toBeNull()
    expect(result.current.isEditing('any')).toBe(false)
  })

  it('startEdit 后 isEditing 返回 true', () => {
    const { result } = renderHook(() => useEditableState())
    act(() => { result.current.startEdit('field_01') })
    expect(result.current.editingField).toBe('field_01')
    expect(result.current.isEditing('field_01')).toBe(true)
  })

  it('stopEdit 后编辑态退出', () => {
    const { result } = renderHook(() => useEditableState())
    act(() => { result.current.startEdit('field_01') })
    act(() => { result.current.stopEdit() })
    expect(result.current.editingField).toBeNull()
    expect(result.current.isEditing('field_01')).toBe(false)
  })

  it('点击新字段时旧字段自动退出（同一时间只有一个 editingField）', () => {
    const { result } = renderHook(() => useEditableState())
    act(() => { result.current.startEdit('field_A') })
    act(() => { result.current.startEdit('field_B') })
    // 只有 B 处于编辑态
    expect(result.current.editingField).toBe('field_B')
    expect(result.current.isEditing('field_A')).toBe(false)
    expect(result.current.isEditing('field_B')).toBe(true)
  })

  it('重复点击同一字段保持编辑态', () => {
    const { result } = renderHook(() => useEditableState())
    act(() => { result.current.startEdit('field_X') })
    act(() => { result.current.startEdit('field_X') })
    expect(result.current.editingField).toBe('field_X')
    expect(result.current.isEditing('field_X')).toBe(true)
  })
})
