// T020: Hooks test — useReportParser
import { describe, it, expect } from 'vitest'

// Test that hooks export correctly (full testing requires component mounting)
describe('useReportParser', () => {
  it('should be importable', async () => {
    const mod = await import('./useReportParser')
    expect(mod.useReportParser).toBeDefined()
    expect(typeof mod.useReportParser).toBe('function')
  })
})

describe('useRecordExport', () => {
  it('should be importable', async () => {
    const mod = await import('./useRecordExport')
    expect(mod.useRecordExport).toBeDefined()
    expect(typeof mod.useRecordExport).toBe('function')
  })
})
