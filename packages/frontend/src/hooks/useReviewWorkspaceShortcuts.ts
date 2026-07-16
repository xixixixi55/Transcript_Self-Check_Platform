import { useEffect } from 'react'

interface ReviewWorkspaceShortcutsOptions {
  onSave: () => void
  previewOpen: boolean
  onClosePreview: () => void
  enabled?: boolean
}

function isEditingElement(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && Boolean(target.closest('input, textarea, select, [contenteditable="true"]'))
}

export function useReviewWorkspaceShortcuts({ onSave, previewOpen, onClosePreview, enabled = true }: ReviewWorkspaceShortcutsOptions) {
  useEffect(() => {
    if (!enabled) return undefined

    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
        event.preventDefault()
        onSave()
        return
      }
      if (event.key === 'Escape' && previewOpen && !isEditingElement(event.target)) {
        event.preventDefault()
        onClosePreview()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [enabled, onClosePreview, onSave, previewOpen])
}
