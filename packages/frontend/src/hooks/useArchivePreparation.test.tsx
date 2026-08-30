import React, { useState } from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ArchiveManifest, InspectionReport } from '@biji/shared/types'
import { useArchivePreparation, usePreviewArchive } from './useArchivePreparation'

const post = vi.hoisted(() => vi.fn())
const get = vi.hoisted(() => vi.fn())
vi.mock('axios', () => ({ default: { post, get } }))

const report = {
  introduction: { case_summary: '合成案件' },
  inspection: { result: {} },
  attachments: { disc_number: '' },
} as InspectionReport
const manifest = {
  manifest_id: 'manifest-1',
  parts: [{
    part_id: 'part-1', filename: '合成案件.rar', size_bytes: 4,
    hash_algorithm: 'sha1', hash_value: 'a'.repeat(40),
  }],
} as ArchiveManifest
const attachmentPreview = {
  columns: [{ key: 'electronic_data', title: '电子数据' }],
  rows: [{ electronic_data: '合成案件.rar', source: 'JC-01内提取', extraction_method: '合成提取方式', md5_hash: 'a'.repeat(32) }],
}

function Harness({ discNumber }: { discNumber: string }) {
  const archive = useArchivePreparation()
  const current = {
    ...report,
    attachments: { ...report.attachments, disc_number: discNumber },
  }
  return (
    <>
      <button onClick={() => void archive.prepare(current, 'context-1')}>开始</button>
      <button onClick={archive.reset}>重置</button>
      <span>{archive.status}</span>
      <span>{String(archive.loading)}</span>
      <span>{archive.manifest?.parts[0].filename}</span>
      <span>{archive.attachmentPreview?.rows[0].source}</span>
      <span>{archive.error}</span>
    </>
  )
}

function PreviewHarness() {
  const [current, setCurrent] = useState<InspectionReport | null>({
    ...report, attachments: { ...report.attachments, disc_number: 'GP20260722-01' },
  })
  const archive = usePreviewArchive(current, setCurrent, 'context-1')
  return <>
    <button onClick={() => setCurrent(value => value ? {
      ...value, attachments: { ...value.attachments, disc_number: 'GP20260722-02' },
    } : value)}>修改光盘编号</button>
    <span>{archive.status}</span>
    <span>{current?.attachments.extract_list?.rows[0]?.electronic_data}</span>
  </>
}

describe('useArchivePreparation', () => {
  beforeEach(() => {
    post.mockReset()
    get.mockReset()
  })

  it('waits for the first disc number without calling WinRAR endpoint', async () => {
    render(<Harness discNumber="" />)
    fireEvent.click(screen.getByText('开始'))
    await waitFor(() => expect(screen.getByText('failed')).toBeTruthy())
    expect(post).not.toHaveBeenCalled()
  })

  it('stores the validated manifest produced during preview', async () => {
    post.mockResolvedValue({ data: { data: { status: 'completed', manifest, attachment_preview: attachmentPreview } } })
    get.mockResolvedValue({ data: { data: { status: 'compressing' } } })
    render(<Harness discNumber="GP20260722-01" />)
    fireEvent.click(screen.getByText('开始'))
    await waitFor(() => expect(screen.getByText('合成案件.rar')).toBeTruthy())
    expect(screen.getByText('ready')).toBeTruthy()
    expect(screen.getByText('JC-01内提取')).toBeTruthy()
    expect(post).toHaveBeenCalledTimes(1)
  })

  it('does not prepare an archive while preview is mounted', () => {
    render(<PreviewHarness />)
    expect(screen.getByText('not_prepared')).toBeTruthy()
    fireEvent.click(screen.getByText('修改光盘编号'))
    expect(post).not.toHaveBeenCalled()
  })

  it('cancels the current archive wait when the preview source is reset', async () => {
    post.mockReturnValue(new Promise(() => undefined))
    render(<Harness discNumber="GP20260722-01" />)
    fireEvent.click(screen.getByText('开始'))
    await waitFor(() => expect(screen.getByText('true')).toBeTruthy())
    fireEvent.click(screen.getByText('重置'))
    await waitFor(() => expect(screen.getByText('not_prepared')).toBeTruthy())
    expect(screen.getByText('false')).toBeTruthy()
    expect(post.mock.calls[0][2].signal.aborted).toBe(true)
  })

  it('aborts the archive wait when the review page unmounts', async () => {
    post.mockReturnValue(new Promise(() => undefined))
    const rendered = render(<Harness discNumber="GP20260722-01" />)
    fireEvent.click(screen.getByText('开始'))
    await waitFor(() => expect(screen.getByText('true')).toBeTruthy())
    rendered.unmount()
    expect(post.mock.calls[0][2].signal.aborted).toBe(true)
  })

  it('allows a failed explicit preparation to be retried', async () => {
    post.mockRejectedValueOnce({ response: { data: { detail: { code: 'ARCHIVE_CONTEXT_INVALID' } } } })
    post.mockResolvedValueOnce({ data: { data: { status: 'completed', manifest, attachment_preview: attachmentPreview } } })
    render(<Harness discNumber="GP20260722-01" />)
    fireEvent.click(screen.getByText('开始'))
    await waitFor(() => expect(screen.getByText('failed')).toBeTruthy())
    fireEvent.click(screen.getByText('开始'))
    await waitFor(() => expect(screen.getByText('ready')).toBeTruthy())
    expect(post).toHaveBeenCalledTimes(2)
  })
})
