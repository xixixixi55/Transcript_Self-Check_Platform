import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import {
  SOURCE_AUTHORIZATION_PREFERENCE_KEY,
  useSourceAuthorizationPreference,
} from './useSourceAuthorizationPreference'

describe('useSourceAuthorizationPreference', () => {
  beforeEach(() => window.localStorage.clear())
  afterEach(() => window.localStorage.clear())

  it('defaults to disabled for a new browser profile', () => {
    const view = renderHook(() => useSourceAuthorizationPreference())

    expect(view.result.current.enabled).toBe(false)
    expect(window.localStorage.getItem(SOURCE_AUTHORIZATION_PREFERENCE_KEY)).toBeNull()
  })

  it('persists the selected mode across hook remounts', () => {
    const first = renderHook(() => useSourceAuthorizationPreference())
    act(() => first.result.current.setEnabled(true))

    expect(first.result.current.enabled).toBe(true)
    expect(window.localStorage.getItem(SOURCE_AUTHORIZATION_PREFERENCE_KEY)).toBe('true')
    first.unmount()

    const second = renderHook(() => useSourceAuthorizationPreference())
    expect(second.result.current.enabled).toBe(true)
    act(() => second.result.current.setEnabled(false))
    expect(window.localStorage.getItem(SOURCE_AUTHORIZATION_PREFERENCE_KEY)).toBe('false')
  })

  it('syncs a preference changed by another browser tab', () => {
    const view = renderHook(() => useSourceAuthorizationPreference())
    act(() => {
      window.localStorage.setItem(SOURCE_AUTHORIZATION_PREFERENCE_KEY, 'true')
      window.dispatchEvent(new StorageEvent('storage', {
        key: SOURCE_AUTHORIZATION_PREFERENCE_KEY, newValue: 'true',
      }))
    })

    expect(view.result.current.enabled).toBe(true)
  })
})
