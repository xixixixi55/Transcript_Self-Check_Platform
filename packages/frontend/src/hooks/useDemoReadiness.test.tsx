import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import { useDemoReadiness } from './useDemoReadiness'

vi.mock('axios', () => ({ default: { get: vi.fn() } }))
const getMock = vi.mocked(axios.get)

describe('useDemoReadiness', () => {
  beforeEach(() => vi.clearAllMocks())

  it('loads the fixed readiness DTO', async () => {
    getMock.mockResolvedValue({
      data: { data: { items: [{
        key: 'backend', label: '后端服务', status: 'ready',
        code: null, guidance: '后端服务可用。',
      }] } },
    })
    const view = renderHook(() => useDemoReadiness())

    await waitFor(() => expect(view.result.current?.items[0].status).toBe('ready'))
    expect(getMock).toHaveBeenCalledWith('/api/v1/demo/readiness')
  })

  it('shows only safe fallback states when the backend is unreachable', async () => {
    getMock.mockRejectedValue(new Error('SYNTHETIC/TEST network failure'))
    const view = renderHook(() => useDemoReadiness())

    await waitFor(() => expect(view.result.current?.items).toHaveLength(3))
    expect(view.result.current?.items.map(item => item.status)).toEqual([
      'unavailable', 'unknown', 'unknown',
    ])
    expect(JSON.stringify(view.result.current)).not.toContain('SYNTHETIC/TEST')
  })
})
