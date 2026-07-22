import React from 'react'
import { render, screen } from '@testing-library/react'
import { beforeAll, describe, expect, it, vi } from 'vitest'
import type { ArchiveManifest } from '@biji/shared/types'
import { ArchiveStatusCard } from './ArchiveStatusCard'

beforeAll(() => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: false, media: query, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }),
  })
})

const manifest = {
  manifest_id: 'manifest-1',
  parts: [{
    part_id: 'part-1',
    part_number: 1,
    filename: '合成案件.rar',
    size_bytes: 123,
    md5: 'a'.repeat(32),
    disc_capacity_bytes: 4_000_000_000,
  }],
} as ArchiveManifest

describe('ArchiveStatusCard', () => {
  it('renders only validated manifest facts and an opaque part download URL', () => {
    render(
      <ArchiveStatusCard
        contextId="context-1"
        status="completed"
        manifest={manifest}
        error={null}
      />,
    )
    expect(screen.getByText('合成案件.rar')).toBeTruthy()
    expect(screen.getByText('123 字节', { exact: false })).toBeTruthy()
    expect(screen.getByText('a'.repeat(32))).toBeTruthy()
    const link = screen.getByRole('link', { name: /下载该 RAR/ })
    expect(link.getAttribute('href')).toContain(
      '/records/archive/context-1/manifests/manifest-1/parts/part-1',
    )
    expect(link.getAttribute('href')).not.toMatch(/[A-Z]:\\/i)
  })
})
