export type ExportGateBlockerCode =
  | 'WINRAR_UNAVAILABLE'
  | 'MATERIAL_TYPE_UNCONFIRMED'
  | 'PRIMARY_SOFTWARE_UNCONFIRMED'
  | 'ODD_PHOTO_COUNT'
  | 'ARCHIVE_MANIFEST_MISSING'
  | 'DISC_SEQUENCE_INVALID'

export interface ExportGateIssue {
  code: ExportGateBlockerCode | string
  field: string
  message: string
}

export interface ExportGateResult {
  allowed: boolean
  blockers: ExportGateIssue[]
  warnings: ExportGateIssue[]
}
