import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import axios from 'axios'
import ElectronicInspectionModulePage from './ElectronicInspectionModulePage'

vi.mock('axios', () => ({ default: { get: vi.fn() } }))
const getMock = vi.mocked(axios.get)

describe('ElectronicInspectionModulePage', () => {
  beforeAll(() => {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: () => ({
        matches: false, media: '', onchange: null,
        addListener: vi.fn(), removeListener: vi.fn(),
        addEventListener: vi.fn(), removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }),
    })
  })

  beforeEach(() => {
    window.localStorage.clear()
    getMock.mockResolvedValue({ data: { data: { items: [] } } })
  })

  it('places a persisted source authorization switch on the homepage', async () => {
    const first = render(<MemoryRouter><ElectronicInspectionModulePage /></MemoryRouter>)
    const toggle = await screen.findByRole('switch', { name: '来源目录校验开关' })

    expect(toggle.getAttribute('aria-checked')).toBe('false')
    fireEvent.click(toggle)
    await waitFor(() => expect(toggle.getAttribute('aria-checked')).toBe('true'))
    expect(window.localStorage.getItem('biji.sourceAuthorization.enabled')).toBe('true')
    first.unmount()

    render(<MemoryRouter><ElectronicInspectionModulePage /></MemoryRouter>)
    expect((await screen.findByRole('switch', { name: '来源目录校验开关' })).getAttribute('aria-checked')).toBe('true')
  })
})
