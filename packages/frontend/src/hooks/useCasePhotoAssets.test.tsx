import { act, renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import axios from 'axios'
import type { UploadFile } from 'antd'
import type { EditLease, OpaqueAssetRef } from '@biji/shared/types'
import { useCasePhotoAssets } from './useCasePhotoAssets'

vi.mock('axios', () => ({ default: { get: vi.fn(), post: vi.fn() } }))

const getMock = vi.mocked(axios.get)
const postMock = vi.mocked(axios.post)
const lease: EditLease = {
  schema_version: 1, lease_id: 'lease-synthetic', case_id: 'case-synthetic',
  session_id: 'session-synthetic', client_instance_id: 'client-synthetic',
  lease_token: 'token-synthetic', last_heartbeat_at: '2026-01-01T00:00:00Z',
  expires_at: '2026-01-01T00:02:00Z', status: 'active', revision: 0,
}

function ref(assetId: string): OpaqueAssetRef {
  return { asset_id: assetId, asset_kind: 'image', fingerprint: `fingerprint-${assetId}`, metadata: { file_name: `${assetId}.png`, media_type: 'image/png' } }
}

describe('useCasePhotoAssets', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    getMock.mockResolvedValue({ data: { data: { items: [] } } } as any)
  })

  it('restores persisted assets and reads binary content through the opaque endpoint', async () => {
    const stored = ref('asset-synthetic-1')
    getMock.mockResolvedValueOnce({ data: { data: { items: [{ ...stored, content_status: 'available' }] } } } as any)
      .mockResolvedValueOnce({ data: new Blob(['SYNTHETIC-IMAGE']) } as any)
    const view = renderHook(() => useCasePhotoAssets({
      caseId: 'case-synthetic', assetRefs: [stored], editingEnabled: true, lease,
      onAssetRefsChange: vi.fn(() => true),
    }))
    await waitFor(() => expect(view.result.current.files[0]?.status).toBe('done'))
    const files = await view.result.current.readFiles()
    expect(files[0].name).toBe('asset-synthetic-1.png')
    expect(files[0]).toBeInstanceOf(File)
    expect(getMock).toHaveBeenLastCalledWith(expect.stringContaining('/assets/asset-synthetic-1'), { responseType: 'blob' })
  })

  it('writes a draft reference only after upload succeeds and preserves the old file on failure', async () => {
    const onAssetRefsChange = vi.fn(() => true)
    const file = new File(['SYNTHETIC-NEW'], 'new.png', { type: 'image/png' })
    const created = { ...ref('asset-synthetic-new'), content_status: 'available' as const }
    postMock.mockResolvedValueOnce({ data: { data: created } } as any)
    const view = renderHook(() => useCasePhotoAssets({
      caseId: 'case-synthetic', assetRefs: [], editingEnabled: true, lease, onAssetRefsChange,
    }))
    await act(async () => { await view.result.current.handleChange([{ uid: 'local-new', name: file.name, originFileObj: file as unknown as NonNullable<UploadFile['originFileObj']> }]) })
    expect(postMock).toHaveBeenCalledTimes(1)
    expect(onAssetRefsChange).toHaveBeenCalledWith([expect.objectContaining({ asset_id: created.asset_id })])
    expect(view.result.current.files[0].uid).toBe(created.asset_id)

    postMock.mockRejectedValueOnce({ response: { data: { detail: { code: 'ASSET_IMAGE_INVALID' } } } })
    const oldFiles = view.result.current.files
    await act(async () => { await view.result.current.handleChange([{ uid: 'local-failed', name: 'failed.png', originFileObj: file as unknown as NonNullable<UploadFile['originFileObj']> }]) })
    expect(view.result.current.files).toEqual(oldFiles)
    expect(view.result.current.assetError).toContain('图片保存失败')
  })

  it('removes an existing persisted reference without mixing another case', async () => {
    const stored = ref('asset-synthetic-2')
    const onAssetRefsChange = vi.fn(() => true)
    getMock.mockResolvedValueOnce({ data: { data: { items: [{ ...stored, content_status: 'available' }] } } } as any)
    const view = renderHook(() => useCasePhotoAssets({
      caseId: 'case-synthetic', assetRefs: [stored], editingEnabled: true, lease, onAssetRefsChange,
    }))
    await waitFor(() => expect(view.result.current.files).toHaveLength(1))
    await act(async () => { await view.result.current.handleChange([]) })
    expect(onAssetRefsChange).toHaveBeenLastCalledWith([])
    expect(view.result.current.files).toEqual([])
  })

  it('blocks export when persisted assets cannot be restored', async () => {
    const stored = ref('asset-synthetic-missing')
    getMock.mockRejectedValueOnce({ response: { data: { detail: { code: 'ASSET_CONTENT_MISSING' } } } })
    const view = renderHook(() => useCasePhotoAssets({
      caseId: 'case-synthetic', assetRefs: [stored], editingEnabled: true, lease,
      onAssetRefsChange: vi.fn(() => true),
    }))
    await waitFor(() => expect(view.result.current.assetError).toContain('图片资产缺失'))
    await act(async () => { await expect(view.result.current.readFiles()).rejects.toThrow('ASSET_CONTENT_MISSING') })
  })
})
