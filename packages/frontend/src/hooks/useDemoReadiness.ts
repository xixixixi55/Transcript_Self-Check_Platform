// Layer 10: FE_Hooks — one-shot Demo capability snapshot with safe fallback.
import { useEffect, useState } from 'react'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'
import type { DemoReadiness, DemoReadinessItem } from '@biji/shared/types'

const unavailableItems: DemoReadinessItem[] = [
  {
    key: 'backend', label: '后端服务', status: 'unavailable',
    code: 'DEMO_BACKEND_UNAVAILABLE', guidance: '请启动或检查后端服务后重试。',
  },
  {
    key: 'winrar', label: 'WinRAR', status: 'unknown',
    code: 'DEMO_WINRAR_UNKNOWN', guidance: '后端恢复后可再次确认 WinRAR 能力。',
  },
  {
    key: 'archive_output', label: '归档输出根', status: 'unknown',
    code: 'DEMO_ARCHIVE_OUTPUT_UNKNOWN', guidance: '后端恢复后可再次确认输出区域。',
  },
]

export function useDemoReadiness() {
  const [readiness, setReadiness] = useState<DemoReadiness | null>(null)

  useEffect(() => {
    let active = true
    axios.get<{ data: DemoReadiness }>(API_ENDPOINTS.DEMO_READINESS)
      .then(response => {
        if (active) setReadiness(response.data.data)
      })
      .catch(() => {
        if (active) setReadiness({ items: unavailableItems })
      })
    return () => { active = false }
  }, [])

  return readiness
}
