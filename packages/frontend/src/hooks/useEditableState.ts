// 第 10 层：FE_Hooks — 点击编辑状态管理
// REQ-019: 每个字段独立控制编辑状态，同一时间最多一个字段处于编辑态
import { useState, useCallback } from 'react'

interface UseEditableStateReturn {
  /** 当前处于编辑态的字段 ID，null 表示无字段在编辑 */
  editingField: string | null
  /** 进入编辑（自动退出其他字段的编辑） */
  startEdit: (fieldId: string) => void
  /** 退出所有编辑 */
  stopEdit: () => void
  /** 判断某字段是否处于编辑态 */
  isEditing: (fieldId: string) => boolean
}

export function useEditableState(): UseEditableStateReturn {
  const [editingField, setEditingField] = useState<string | null>(null)

  const startEdit = useCallback((fieldId: string) => {
    setEditingField(fieldId)
  }, [])

  const stopEdit = useCallback(() => {
    setEditingField(null)
  }, [])

  const isEditing = useCallback(
    (fieldId: string) => editingField === fieldId,
    [editingField],
  )

  return { editingField, startEdit, stopEdit, isEditing }
}
