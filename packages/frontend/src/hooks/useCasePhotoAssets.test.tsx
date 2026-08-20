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
      onAssetRefsChange: vi.fn(async () => true),
    }))
    await waitFor(() => expect(view.result.current.files[0]?.status).toBe('done'))
    const files = await view.result.current.readFiles()
    expect(files[0].name).toBe('asset-synthetic-1.png')
    expect(files[0]).toBeInstanceOf(File)
    expect(getMock).toHaveBeenLastCalledWith(expect.stringContaining('/assets/asset-synthetic-1'), { responseType: 'blob' })
  })

  it('writes a draft reference only after upload succeeds and preserves the old file on failure', async () => {
    const onAssetRefsChange = vi.fn(async () => true)
    const file = new File(['SYNTHETIC-NEW'], 'new.png', { type: 'image/png' })
    const created = { ...ref('asset-synthetic-new'), content_status: 'available' as const }
    postMock.mockResolvedValueOnce({ data: { data: created } } as any)
    const view = renderHook(() => useCasePhotoAssets({
      caseId: 'case-synthetic', assetRefs: [], editingEnabled: true, lease, onAssetRefsChange,
    }))
    await act(async () => { await view.result.current.handleChange([{ uid: 'local-new', name: file.name, originFileObj: file as unknown as NonNullable<UploadFile['originFileObj']> }]) })
    expect(postMock).toHaveBeenCalledTimes(1)
    expect(onAssetRefsChange).toHaveBeenCalledWith(
      [expect.objectContaining({ asset_id: created.asset_id })], [],
    )
    expect(view.result.current.files[0].uid).toBe(created.asset_id)

    postMock.mockRejectedValueOnce({ response: { data: { detail: { code: 'ASSET_IMAGE_INVALID' } } } })
    const oldFiles = view.result.current.files
    await act(async () => { await view.result.current.handleChange([{ uid: 'local-failed', name: 'failed.png', originFileObj: file as unknown as NonNullable<UploadFile['originFileObj']> }]) })
    expect(view.result.current.files).toEqual(oldFiles)
    expect(view.result.current.assetError).toContain('图片保存失败')
  })

  it('bounds upload and export-read concurrency for a 202-image batch', async () => {
    let activeUploads = 0
    let maxUploads = 0
    postMock.mockImplementation(async (_url, body) => {
      const file = (body as FormData).get('photo') as File
      activeUploads += 1
      maxUploads = Math.max(maxUploads, activeUploads)
      await new Promise(resolve => setTimeout(resolve, 1))
      activeUploads -= 1
      return { data: { data: { ...ref(`asset-${file.name}`), content_status: 'available' } } } as any
    })
    const onAssetRefsChange = vi.fn(async () => true)
    const view = renderHook(() => useCasePhotoAssets({
      caseId: 'case-synthetic', assetRefs: [], editingEnabled: true, lease, onAssetRefsChange,
    }))
    const files = Array.from({ length: 202 }, (_, index) => {
      const file = new File(['SYNTHETIC'], `pic${index + 1}.png`, { type: 'image/png' })
      return { uid: `local-${index + 1}`, name: file.name, originFileObj: file as unknown as NonNullable<UploadFile['originFileObj']> }
    })

    await act(async () => { await view.result.current.handleChange(files) })

    expect(postMock).toHaveBeenCalledTimes(202)
    expect(maxUploads).toBe(4)
    expect(onAssetRefsChange).toHaveBeenCalledTimes(1)
    expect(view.result.current.files).toHaveLength(202)
    expect(view.result.current.files[0].uid).toBe('asset-pic1.png')
    expect(view.result.current.files[201].uid).toBe('asset-pic202.png')
    const boundRefs = (onAssetRefsChange.mock.calls[0] as unknown as [OpaqueAssetRef[]])[0]
    expect([boundRefs[0].asset_id, boundRefs[201].asset_id]).toEqual(['asset-pic1.png', 'asset-pic202.png'])

    let activeReads = 0
    let maxReads = 0
    getMock.mockReset().mockImplementation(async () => {
      activeReads += 1
      maxReads = Math.max(maxReads, activeReads)
      await new Promise(resolve => setTimeout(resolve, 1))
      activeReads -= 1
      return { data: new Blob(['SYNTHETIC']) } as any
    })
    const restored = await view.result.current.readFiles()
    expect(restored).toHaveLength(202)
    expect(maxReads).toBe(4)
    expect([restored[0].name, restored[201].name]).toEqual(['asset-pic1.png.png', 'asset-pic202.png.png'])
  })

  it('retries only failed files after a partial batch upload failure', async () => {
    const files = [1, 2, 3].map(index => {
      const file = new File(['SYNTHETIC'], `retry-${index}.png`, { type: 'image/png' })
      return { uid: `local-retry-${index}`, name: file.name, originFileObj: file as unknown as NonNullable<UploadFile['originFileObj']> }
    })
    const attempts = new Map<string, number>()
    postMock.mockImplementation(async (_url, body) => {
      const file = (body as FormData).get('photo') as File
      attempts.set(file.name, (attempts.get(file.name) || 0) + 1)
      if (file.name === 'retry-2.png' && attempts.get(file.name) === 1) throw new Error('SYNTHETIC_UPLOAD_FAILED')
      return { data: { data: { ...ref(`asset-${file.name}`), content_status: 'available' } } } as any
    })
    const onAssetRefsChange = vi.fn(async () => true)
    const view = renderHook(() => useCasePhotoAssets({
      caseId: 'case-synthetic', assetRefs: [], editingEnabled: true, lease, onAssetRefsChange,
    }))

    await act(async () => { await view.result.current.handleChange(files) })
    expect(onAssetRefsChange).not.toHaveBeenCalled()
    await act(async () => { await view.result.current.handleChange(files) })

    expect(attempts).toEqual(new Map([
      ['retry-1.png', 1], ['retry-2.png', 2], ['retry-3.png', 1],
    ]))
    expect(onAssetRefsChange).toHaveBeenCalledTimes(1)
    expect(view.result.current.files.map(file => file.uid)).toEqual([
      'asset-retry-1.png', 'asset-retry-2.png', 'asset-retry-3.png',
    ])
  })

  it('coalesces repeated Ant Design callbacks for one two-image selection', async () => {
    const onAssetRefsChange = vi.fn(async () => true)
    const firstFile = new File(['SYNTHETIC-FRONT'], 'front.png', { type: 'image/png' })
    const secondFile = new File(['SYNTHETIC-BACK'], 'back.png', { type: 'image/png' })
    const firstAsset = { ...ref('asset-synthetic-front'), content_status: 'available' as const }
    const secondAsset = { ...ref('asset-synthetic-back'), content_status: 'available' as const }
    const uploadResolvers: Array<(value: unknown) => void> = []
    postMock.mockImplementation(() => new Promise(resolve => { uploadResolvers.push(resolve) }) as any)
    const view = renderHook(() => useCasePhotoAssets({
      caseId: 'case-synthetic', assetRefs: [], editingEnabled: true, lease, onAssetRefsChange,
    }))
    const files = [
      { uid: 'local-front', name: firstFile.name, originFileObj: firstFile as unknown as NonNullable<UploadFile['originFileObj']> },
      { uid: 'local-back', name: secondFile.name, originFileObj: secondFile as unknown as NonNullable<UploadFile['originFileObj']> },
    ]
    let uploadPromise!: Promise<boolean>
    act(() => { uploadPromise = view.result.current.handleChange(files) })
    await waitFor(() => expect(postMock).toHaveBeenCalledTimes(2))
    await act(async () => { await view.result.current.handleChange(files) })
    expect(postMock).toHaveBeenCalledTimes(2)

    await act(async () => {
      uploadResolvers[0]({ data: { data: firstAsset } })
      uploadResolvers[1]({ data: { data: secondAsset } })
      await uploadPromise
    })
    expect(onAssetRefsChange).toHaveBeenCalledTimes(1)
    const savedRefs = (onAssetRefsChange.mock.calls[0] as unknown as [OpaqueAssetRef[]])[0]
    expect(savedRefs.map(item => item.asset_id)).toEqual([
      firstAsset.asset_id, secondAsset.asset_id,
    ])
    expect(view.result.current.files).toHaveLength(2)
  })

  it('ignores a late callback with the local file list after upload completes', async () => {
    const onAssetRefsChange = vi.fn(async () => true)
    const file = new File(['SYNTHETIC-LATE-CALLBACK'], 'late.png', { type: 'image/png' })
    const created = { ...ref('asset-synthetic-late'), content_status: 'available' as const }
    postMock.mockReset()
    postMock.mockResolvedValueOnce({ data: { data: created } } as any)
    const view = renderHook(() => useCasePhotoAssets({
      caseId: 'case-synthetic', assetRefs: [], editingEnabled: true, lease, onAssetRefsChange,
    }))
    const localFiles = [{
      uid: 'local-late', name: file.name,
      originFileObj: file as unknown as NonNullable<UploadFile['originFileObj']>,
    }]

    await act(async () => { await view.result.current.handleChange(localFiles) })
    await act(async () => { await view.result.current.handleChange(localFiles) })

    expect(postMock).toHaveBeenCalledTimes(1)
    expect(onAssetRefsChange).toHaveBeenCalledTimes(1)
    expect(view.result.current.files[0].uid).toBe(created.asset_id)
  })

  it('removes an existing persisted reference without mixing another case', async () => {
    const stored = ref('asset-synthetic-2')
    const onAssetRefsChange = vi.fn(async () => true)
    getMock.mockResolvedValueOnce({ data: { data: { items: [{ ...stored, content_status: 'available' }] } } } as any)
    const view = renderHook(() => useCasePhotoAssets({
      caseId: 'case-synthetic', assetRefs: [stored], editingEnabled: true, lease, onAssetRefsChange,
    }))
    await waitFor(() => expect(view.result.current.files).toHaveLength(1))
    await act(async () => { await view.result.current.handleChange([]) })
    expect(onAssetRefsChange).toHaveBeenLastCalledWith([], [stored])
    expect(view.result.current.files).toEqual([])
  })

  it('blocks export when persisted assets cannot be restored', async () => {
    const stored = ref('asset-synthetic-missing')
    getMock.mockRejectedValueOnce({ response: { data: { detail: { code: 'ASSET_CONTENT_MISSING' } } } })
    const view = renderHook(() => useCasePhotoAssets({
      caseId: 'case-synthetic', assetRefs: [stored], editingEnabled: true, lease,
      onAssetRefsChange: vi.fn(async () => true),
    }))
    await waitFor(() => expect(view.result.current.assetError).toContain('图片资产缺失'))
    await act(async () => { await expect(view.result.current.readFiles()).rejects.toThrow('ASSET_CONTENT_MISSING') })
  })

  it('waits for the immediate draft binding save before an upload becomes idle', async () => {
    const file = new File(['SYNTHETIC-IMMEDIATE-SAVE'], 'immediate.png', { type: 'image/png' })
    const created = { ...ref('asset-synthetic-immediate'), content_status: 'available' as const }
    let resolveSave: ((saved: boolean) => void) | undefined
    const onAssetRefsChange = vi.fn(() => new Promise<boolean>(resolve => { resolveSave = resolve }))
    postMock.mockResolvedValueOnce({ data: { data: created } } as any)
    const view = renderHook(() => useCasePhotoAssets({
      caseId: 'case-synthetic', assetRefs: [], editingEnabled: true, lease, onAssetRefsChange,
    }))

    let upload!: Promise<boolean>
    act(() => {
      upload = view.result.current.handleChange([{
        uid: 'local-immediate', name: file.name,
        originFileObj: file as unknown as NonNullable<UploadFile['originFileObj']>,
      }])
    })
    await waitFor(() => expect(onAssetRefsChange).toHaveBeenCalledTimes(1))
    expect(view.result.current.uploading).toBe(true)

    await act(async () => {
      resolveSave?.(true)
      await upload
    })
    expect(view.result.current.uploading).toBe(false)
    await expect(view.result.current.waitForIdle()).resolves.toBe(true)
  })

  it('lets standalone Word stop waiting for a stalled photo operation', async () => {
    const file = new File(['SYNTHETIC-STALLED-SAVE'], 'stalled.png', { type: 'image/png' })
    const created = { ...ref('asset-synthetic-stalled'), content_status: 'available' as const }
    let resolveSave: ((saved: boolean) => void) | undefined
    const onAssetRefsChange = vi.fn(() => new Promise<boolean>(resolve => { resolveSave = resolve }))
    postMock.mockResolvedValueOnce({ data: { data: created } } as any)
    const view = renderHook(() => useCasePhotoAssets({
      caseId: 'case-synthetic', assetRefs: [], editingEnabled: true, lease, onAssetRefsChange,
    }))
    let upload!: Promise<boolean>

    act(() => {
      upload = view.result.current.handleChange([{
        uid: 'local-stalled', name: file.name,
        originFileObj: file as unknown as NonNullable<UploadFile['originFileObj']>,
      }])
    })
    await waitFor(() => expect(onAssetRefsChange).toHaveBeenCalledTimes(1))

    await expect(view.result.current.waitForIdle(5)).resolves.toBe(false)
    expect(view.result.current.uploading).toBe(true)

    await act(async () => {
      resolveSave?.(true)
      await upload
    })
  })

  it('reports a non-idle-safe result when the immediate draft binding save fails', async () => {
    const file = new File(['SYNTHETIC-FAILED-BINDING'], 'failed-binding.png', { type: 'image/png' })
    const created = { ...ref('asset-synthetic-failed-binding'), content_status: 'available' as const }
    postMock.mockResolvedValueOnce({ data: { data: created } } as any)
    const onAssetRefsChange = vi.fn()
      .mockResolvedValueOnce(false)
      .mockResolvedValueOnce(true)
    const view = renderHook(() => useCasePhotoAssets({
      caseId: 'case-synthetic', assetRefs: [], editingEnabled: true, lease,
      onAssetRefsChange,
    }))

    await act(async () => {
      await view.result.current.handleChange([{
        uid: 'local-failed-binding', name: file.name,
        originFileObj: file as unknown as NonNullable<UploadFile['originFileObj']>,
      }])
    })

    await expect(view.result.current.waitForIdle()).resolves.toBe(false)
    expect(view.result.current.navigationUnsafe).toBe(true)
    expect(view.result.current.files[0].uid).toBe(created.asset_id)
    expect(view.result.current.assetError).toContain('图片保存失败')

    await act(async () => { await view.result.current.handleChange(view.result.current.files) })

    expect(postMock).toHaveBeenCalledTimes(1)
    expect(onAssetRefsChange).toHaveBeenNthCalledWith(
      2, [expect.objectContaining({ asset_id: created.asset_id })], [],
    )
    await expect(view.result.current.waitForIdle()).resolves.toBe(true)
    expect(view.result.current.navigationUnsafe).toBe(false)
  })

  it('distinguishes a real concurrent photo-list conflict', async () => {
    const file = new File(['SYNTHETIC-CONFLICT'], 'conflict.png', { type: 'image/png' })
    postMock.mockResolvedValueOnce({ data: { data: {
      ...ref('asset-synthetic-conflict'), content_status: 'available',
    } } } as any)
    const conflict: any = new Error('PHOTO_BINDING_CONFLICT')
    conflict.response = { data: { detail: { code: 'PHOTO_BINDING_CONFLICT' } } }
    const view = renderHook(() => useCasePhotoAssets({
      caseId: 'case-synthetic', assetRefs: [], editingEnabled: true, lease,
      onAssetRefsChange: vi.fn(async () => { throw conflict }),
    }))

    await act(async () => {
      await view.result.current.handleChange([{
        uid: 'local-conflict', name: file.name,
        originFileObj: file as unknown as NonNullable<UploadFile['originFileObj']>,
      }])
    })

    expect(view.result.current.assetError).toContain('图片列表已被另一会话修改')
    expect(view.result.current.navigationUnsafe).toBe(true)
  })

  it('recovers available registry images that are not yet bound to the draft', async () => {
    const first = { ...ref('asset-synthetic-orphan-1'), content_status: 'available' as const }
    const second = { ...ref('asset-synthetic-orphan-2'), content_status: 'available' as const }
    const onAssetRefsChange = vi.fn(async () => true)
    getMock.mockResolvedValueOnce({ data: { data: { items: [first, second] } } } as any)

    const view = renderHook(() => useCasePhotoAssets({
      caseId: 'case-synthetic', assetRefs: [], editingEnabled: true, lease, onAssetRefsChange,
    }))

    await waitFor(() => expect(onAssetRefsChange).toHaveBeenCalledTimes(1))
    const recovered = (onAssetRefsChange.mock.calls[0] as unknown as [OpaqueAssetRef[]])[0]
    expect(recovered.map(item => item.asset_id)).toEqual([first.asset_id, second.asset_id])
    await waitFor(() => expect(view.result.current.files).toHaveLength(2))
  })
})
