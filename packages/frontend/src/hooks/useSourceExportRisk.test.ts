import { describe, expect, it, vi } from 'vitest'
import { runWithSourceExportRiskConfirmation } from './useSourceExportRisk'

describe('source export risk confirmation', () => {
  it('exports available sources without a warning', async () => {
    const confirm = vi.fn()
    const exportAction = vi.fn().mockResolvedValue(true)

    await expect(runWithSourceExportRiskConfirmation(
      'available', exportAction, confirm,
    )).resolves.toBe(true)

    expect(confirm).not.toHaveBeenCalled()
    expect(exportAction).toHaveBeenCalledOnce()
  })

  it('keeps pending warning visible until the user confirms or cancels', async () => {
    const exportAction = vi.fn().mockResolvedValue(true)
    const cancel = vi.fn().mockReturnValue(false)

    await expect(runWithSourceExportRiskConfirmation(
      'pending', exportAction, cancel,
    )).resolves.toBe(false)

    expect(cancel).toHaveBeenCalledWith(expect.stringContaining('确认后仍可导出 Word'))
    expect(exportAction).not.toHaveBeenCalled()

    const confirm = vi.fn().mockReturnValue(true)
    await expect(runWithSourceExportRiskConfirmation(
      'pending', exportAction, confirm,
    )).resolves.toBe(true)
    expect(exportAction).toHaveBeenCalledOnce()
  })

  it('uses a stronger warning for a source that requires reselection', async () => {
    const exportAction = vi.fn().mockResolvedValue(true)
    const confirm = vi.fn().mockReturnValue(true)

    await expect(runWithSourceExportRiskConfirmation(
      'requires_reselection', exportAction, confirm,
    )).resolves.toBe(true)

    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('来源已经变化、不可用或需要重新选择'))
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('确认风险后仍可导出 Word'))
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('仍要继续导出 Word'))
    expect(exportAction).toHaveBeenCalledOnce()
  })
})
