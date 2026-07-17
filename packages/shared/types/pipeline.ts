export type PipelineMode = 'legacy' | 'shadow' | 'canonical'

export interface RuntimeVersions {
  schema_version: string
  adapter_version: string
  template_version: string
  plan_version: string
}

export interface PipelineSettings {
  mode: PipelineMode
  source: 'default' | 'environment' | 'invalid_fallback'
  invalid_value?: string
  versions: RuntimeVersions
  cache_namespace: string
}

export type PipelineRunStatus =
  | 'legacy_formal_output'
  | 'shadow_compare_only'
  | 'canonical_not_enabled'
