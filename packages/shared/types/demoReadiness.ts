export type DemoReadinessState =
  | 'ready'
  | 'not_configured'
  | 'unavailable'
  | 'unknown'

export type DemoReadinessKey =
  | 'backend'
  | 'source_authorization'
  | 'winrar'
  | 'archive_output'

export interface DemoReadinessItem {
  key: DemoReadinessKey
  label: string
  status: DemoReadinessState
  code: string | null
  guidance: string
}

export interface DemoReadiness {
  items: DemoReadinessItem[]
}
