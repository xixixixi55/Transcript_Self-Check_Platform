import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
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
    disc_number: 'GP20260718-01',
    disc_capacity_bytes: 4_000_000_000,
  }],
} as ArchiveManifest

const multiVolumeManifest = {
  manifest_id: 'manifest-2',
  parts: [
    {
      part_id: 'part-1', part_number: 1, filename: '合成案件.part1.rar',
      size_bytes: 123, md5: 'a'.repeat(32), disc_number: 'GP20260718-01',
      disc_capacity_bytes: 4_000_000_000,
    },
    {
      part_id: 'part-2', part_number: 2, filename: '合成案件.part2.rar',
      size_bytes: 456, md5: 'b'.repeat(32), disc_number: 'GP20260718-02',
      disc_capacity_bytes: 4_000_000_000,
    },
  ],
} as ArchiveManifest

describe('ArchiveStatusCard', () => {
  it('requires an explicit archive preparation action after preview', () => {
    const onPrepare = vi.fn()
    render(
      <ArchiveStatusCard
        contextId="context-1"
        status="not_prepared"
        manifest={null}
        error={null}
        onPrepare={onPrepare}
      />,
    )
    expect(screen.getByText('归档尚未准备')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '开始准备归档' }))
    expect(onPrepare).toHaveBeenCalledTimes(1)
  })

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

  it('shows each archive volume mapped to its disc number', () => {
    render(
      <ArchiveStatusCard
        contextId="context-1"
        status="completed"
        manifest={multiVolumeManifest}
        error={null}
      />,
    )
    expect(screen.getByText('合成案件.part1.rar')).toBeTruthy()
    expect(screen.getByText('合成案件.part2.rar')).toBeTruthy()
    expect(screen.getByText('GP20260718-01')).toBeTruthy()
    expect(screen.getByText('GP20260718-02')).toBeTruthy()
  })

  it('renders completed workbench archive results with opaque part downloads', () => {
    render(
      <ArchiveStatusCard
        contextId={null}
        taskId="archive-task-1"
        status="completed"
        manifest={null}
        resultParts={[{
          part_id: 'part-1', filename: '合成案件.part1.rar', size_bytes: 123,
          md5: 'a'.repeat(32), disc_number: 'GP20260718-01', disc_date: '2026-07-18',
        }]}
        error={null}
      />,
    )
    expect(screen.getByText('GP20260718-01')).toBeTruthy()
    expect(screen.getByRole('link', { name: /下载该 RAR/ }).getAttribute('href')).toContain(
      '/workbench/tasks/archive-task-1/result/parts/part-1',
    )
  })
})
