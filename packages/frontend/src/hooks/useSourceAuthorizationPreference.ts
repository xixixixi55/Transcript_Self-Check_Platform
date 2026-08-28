import { useCallback, useEffect, useState } from 'react'

export const SOURCE_AUTHORIZATION_PREFERENCE_KEY = 'biji.sourceAuthorization.enabled'

const DEFAULT_SOURCE_AUTHORIZATION_ENABLED = false
const SOURCE_AUTHORIZATION_PREFERENCE_EVENT = 'biji:source-authorization-preference'

function readStoredPreference(): boolean {
  if (typeof window === 'undefined') return DEFAULT_SOURCE_AUTHORIZATION_ENABLED
  try {
    const stored = window.localStorage.getItem(SOURCE_AUTHORIZATION_PREFERENCE_KEY)
    if (stored === 'true') return true
    if (stored === 'false') return false
  } catch {
    // 在受限的浏览器上下文中，存储功能可能不可用。
  }
  return DEFAULT_SOURCE_AUTHORIZATION_ENABLED
}

export function getSourceAuthorizationEnabled(): boolean {
  return readStoredPreference()
}

export function setSourceAuthorizationEnabled(enabled: boolean): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(
      SOURCE_AUTHORIZATION_PREFERENCE_KEY,
      enabled ? 'true' : 'false',
    )
  } catch {
    // 内存中的 Hook 状态仍反映用户当前的选择。
  }
  window.dispatchEvent(new Event(SOURCE_AUTHORIZATION_PREFERENCE_EVENT))
}

export function useSourceAuthorizationPreference() {
  const [enabled, setEnabled] = useState(getSourceAuthorizationEnabled)
  const update = useCallback((nextEnabled: boolean) => {
    setSourceAuthorizationEnabled(nextEnabled)
    setEnabled(nextEnabled)
  }, [])

  useEffect(() => {
    const sync = () => setEnabled(getSourceAuthorizationEnabled())
    window.addEventListener('storage', sync)
    window.addEventListener(SOURCE_AUTHORIZATION_PREFERENCE_EVENT, sync)
    return () => {
      window.removeEventListener('storage', sync)
      window.removeEventListener(SOURCE_AUTHORIZATION_PREFERENCE_EVENT, sync)
    }
  }, [])

  return { enabled, setEnabled: update }
}
