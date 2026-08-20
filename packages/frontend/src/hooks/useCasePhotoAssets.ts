// Layer 10: FE_Hooks — persistent case-bound photo upload and recovery.
import { useCallback, useEffect, useRef, useState } from 'react'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'
import type { CaseAssetList, CaseAssetRecord, EditLease, OpaqueAssetRef } from '@biji/shared/types'
import type { UploadFile } from 'antd'

interface Options {
  caseId: string
  assetRefs: OpaqueAssetRef[]
  draftRevision?: number
  editingEnabled: boolean
  lease: EditLease | null
  onAssetRefsChange: (refs: OpaqueAssetRef[], expectedRefs: OpaqueAssetRef[]) => Promise<boolean>
}

function errorMessage(error: any): string {
  const code = error?.response?.data?.detail?.code || error?.message
  return code === 'ASSET_CONTENT_MISSING'
    ? '图片资产缺失，请重新上传。'
    : code === 'ASSET_CONTENT_CORRUPT'
      ? '图片资产已损坏，请重新上传。'
      : code === 'LEASE_NOT_ACTIVE' || code === 'LEASE_EXPIRED'
        ? '编辑租约已失效，图片修改未保存。'
        : code === 'PHOTO_BINDING_CONFLICT'
          ? '图片列表已被另一会话修改，请重新读取案件后再保存。'
        : '图片保存失败，当前输入仍保留，请重试。'
}

function refForRecord(record: CaseAssetRecord): OpaqueAssetRef {
  return {
    asset_id: record.asset_id, asset_kind: record.asset_kind,
    fingerprint: record.fingerprint, metadata: record.metadata,
  }
}

function fileName(ref: OpaqueAssetRef): string {
  const value = ref.metadata?.file_name
  return typeof value === 'string' && value ? value : `${ref.asset_id}.jpg`
}

function fileType(ref: OpaqueAssetRef): string {
  const value = ref.metadata?.media_type
  return typeof value === 'string' ? value : 'image/jpeg'
}

function fileForRef(caseId: string, ref: OpaqueAssetRef): UploadFile {
  return {
    uid: ref.asset_id,
    name: fileName(ref),
    type: fileType(ref),
    status: 'done',
    url: API_ENDPOINTS.WORKBENCH_CASE_ASSET(caseId, ref.asset_id),
  }
}

const PHOTO_IO_CONCURRENCY = 4

async function mapPhotoIo<T, R>(items: T[], operation: (item: T) => Promise<R>): Promise<R[]> {
  const results = new Array<R>(items.length)
  let cursor = 0
  let failed = false
  let failure: unknown
  const worker = async () => {
    while (!failed) {
      const index = cursor++
      if (index >= items.length) return
      try {
        results[index] = await operation(items[index])
      } catch (error) {
        failed = true
        failure = error
      }
    }
  }
  await Promise.all(Array.from(
    { length: Math.min(PHOTO_IO_CONCURRENCY, items.length) },
    worker,
  ))
  if (failed) throw failure
  return results
}

export function useCasePhotoAssets(options: Options) {
  const { caseId, assetRefs, draftRevision, editingEnabled, lease, onAssetRefsChange } = options
  const [files, setFiles] = useState<UploadFile[]>([])
  const [assetError, setAssetError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [bindingSaveFailed, setBindingSaveFailed] = useState(false)
  const uploadingRef = useRef(false)
  const completedUploadsRef = useRef(new Map<string, OpaqueAssetRef>())
  const pendingOperationRef = useRef<Promise<boolean> | null>(null)
  const lastOperationSucceededRef = useRef(true)
  const requestSequence = useRef(0)
  const filesRef = useRef<UploadFile[]>([])
  const refsRef = useRef(assetRefs)
  const onAssetRefsChangeRef = useRef(onAssetRefsChange)
  const syncedRefsKey = useRef<string | null>(null)
  const savedDraftRevisionRef = useRef(draftRevision)
  const refsKey = assetRefs.map(ref => `${ref.asset_id}:${ref.fingerprint || ''}`).join('|')

  useEffect(() => {
    completedUploadsRef.current.clear()
    lastOperationSucceededRef.current = true
    setBindingSaveFailed(false)
  }, [caseId])
  useEffect(() => {
    if (savedDraftRevisionRef.current === draftRevision) return
    savedDraftRevisionRef.current = draftRevision
    lastOperationSucceededRef.current = true
    setBindingSaveFailed(false)
  }, [draftRevision])
  useEffect(() => { onAssetRefsChangeRef.current = onAssetRefsChange }, [onAssetRefsChange])
  useEffect(() => {
    const scopedRefsKey = `${caseId}:${refsKey}`
    if (syncedRefsKey.current === scopedRefsKey) return
    refsRef.current = assetRefs
    syncedRefsKey.current = scopedRefsKey
  }, [caseId, refsKey])
  useEffect(() => { filesRef.current = files }, [files])

  const beginOperation = useCallback((work: () => Promise<boolean>): Promise<boolean> => {
    uploadingRef.current = true
    lastOperationSucceededRef.current = false
    setUploading(true)
    const operation = work().then(succeeded => {
      lastOperationSucceededRef.current = succeeded
      setBindingSaveFailed(!succeeded)
      return succeeded
    }).catch(error => {
      setBindingSaveFailed(true)
      setAssetError(errorMessage(error))
      return false
    })
    pendingOperationRef.current = operation
    void operation.finally(() => {
      if (pendingOperationRef.current === operation) pendingOperationRef.current = null
      uploadingRef.current = false
      setUploading(false)
    })
    return operation
  }, [])

  useEffect(() => {
    const sequence = ++requestSequence.current
    let active = true
    setFiles([])
    setAssetError(null)
    axios.get<{ data: CaseAssetList }>(API_ENDPOINTS.WORKBENCH_CASE_ASSETS(caseId))
      .then(response => {
        if (!active || sequence !== requestSequence.current) return
        const items = response.data.data.items
        const records = new Map(items.map(item => [item.asset_id, item]))
        const referencedIds = new Set(assetRefs.map(ref => ref.asset_id))
        const recoveredRefs = editingEnabled
          ? items.filter(item => item.content_status === 'available' && !referencedIds.has(item.asset_id)).map(refForRecord)
          : []
        const effectiveRefs = [...assetRefs, ...recoveredRefs]
        for (const ref of recoveredRefs) completedUploadsRef.current.set(ref.asset_id, ref)
        const restored = effectiveRefs.map(ref => {
          const record = records.get(ref.asset_id)
          const available = record?.content_status === 'available'
          return {
            uid: ref.asset_id, name: fileName(ref), type: fileType(ref), status: available ? 'done' : 'error',
            url: API_ENDPOINTS.WORKBENCH_CASE_ASSET(caseId, ref.asset_id),
          } as UploadFile
        })
        if (restored.some(file => file.status === 'error')) setAssetError('部分图片资产无法读取，请重新上传后再导出。')
        refsRef.current = effectiveRefs
        setFiles(restored)
        if (recoveredRefs.length) {
          void beginOperation(async () => {
            try {
              const saved = await onAssetRefsChangeRef.current(effectiveRefs, assetRefs)
              if (!saved) refsRef.current = assetRefs
              if (!saved && active) setAssetError('已恢复未绑定图片，但草稿保存未完成，请重试保存。')
              return saved
            } catch (error) {
              refsRef.current = assetRefs
              throw error
            }
          })
        }
      })
      .catch(error => {
        if (active && sequence === requestSequence.current) setAssetError(errorMessage(error))
      })
    return () => { active = false }
  }, [beginOperation, caseId, editingEnabled, refsKey])

  const upload = useCallback(async (file: UploadFile): Promise<CaseAssetRecord> => {
    if (!file.originFileObj || !lease) throw new Error('LEASE_NOT_ACTIVE')
    const body = new FormData()
    body.append('photo', file.originFileObj)
    body.append('lease_id', lease.lease_id)
    body.append('lease_token', lease.lease_token)
    const response = await axios.post<{ data: CaseAssetRecord }>(
      API_ENDPOINTS.WORKBENCH_CASE_ASSETS(caseId), body,
    )
    return response.data.data
  }, [caseId, lease])

  const applyChange = useCallback(async (nextFiles: UploadFile[]): Promise<boolean> => {
    const completedUploads = completedUploadsRef.current
    const newFiles = nextFiles.filter(file => file.originFileObj
      && !refsRef.current.some(ref => ref.asset_id === file.uid)
      && !completedUploads.has(file.uid))
    if (!newFiles.length) {
      const nextRefs = nextFiles.flatMap(file => {
        const completed = completedUploads.get(file.uid)
        return completed ? [completed] : refsRef.current.filter(ref => ref.asset_id === file.uid)
      })
      // Ant Design can deliver an already queued callback after the upload
      // promise has completed. If its local uid list resolves to the exact
      // persisted refs currently shown, it is not a new user edit.
      if (nextFiles.some(file => completedUploads.has(file.uid))
        && JSON.stringify(nextRefs) === JSON.stringify(refsRef.current)) return true
      const restored = nextFiles.map(file => {
        const completed = completedUploads.get(file.uid)
        return completed ? fileForRef(caseId, completed) : file
      })
      filesRef.current = restored
      setFiles(restored)
      if (JSON.stringify(nextRefs) !== JSON.stringify(refsRef.current)) {
        const previousRefs = refsRef.current
        refsRef.current = nextRefs
        if (!await onAssetRefsChangeRef.current(nextRefs, previousRefs)) {
          refsRef.current = previousRefs
          setAssetError('图片引用尚未保存到草稿，请重试保存。')
          return false
        }
      }
      return true
    }
    setAssetError(null)
    setFiles(nextFiles.map(file => newFiles.some(item => item.uid === file.uid) ? { ...file, status: 'uploading' } : file))
    const previousRefs = refsRef.current
    try {
      const uploaded = await mapPhotoIo(newFiles, async file => {
        const created = refForRecord(await upload(file))
        completedUploads.set(file.uid, created)
        completedUploads.set(created.asset_id, created)
        return [file.uid, created] as const
      })
      const uploadedByUid = new Map(uploaded)
      const nextRefs = nextFiles.flatMap(file => {
        const created = uploadedByUid.get(file.uid) || completedUploads.get(file.uid)
        if (created) return [created]
        return refsRef.current.filter(ref => ref.asset_id === file.uid)
      })
      const restored = nextFiles.map(file => {
        const created = uploadedByUid.get(file.uid) || completedUploads.get(file.uid)
        return created ? fileForRef(caseId, created) : file
      })
      refsRef.current = nextRefs
      filesRef.current = restored
      setFiles(restored)
      if (!await onAssetRefsChangeRef.current(nextRefs, previousRefs)) throw new Error('DRAFT_SAVE_FAILED')
      return true
    } catch (error) {
      // The uploaded files remain available for retry, but the compare-and-set
      // baseline must stay at the last successfully bound photo list.
      refsRef.current = previousRefs
      setFiles(filesRef.current)
      setAssetError(errorMessage(error))
      return false
    }
  }, [caseId, upload])

  const handleChange = useCallback((nextFiles: UploadFile[]): Promise<boolean> => {
    if (!editingEnabled || uploadingRef.current) return Promise.resolve(false)
    return beginOperation(() => applyChange(nextFiles))
  }, [applyChange, beginOperation, editingEnabled])

  const waitForIdle = useCallback(async (maxWaitMs?: number): Promise<boolean> => {
    const wait = async () => {
      while (pendingOperationRef.current) await pendingOperationRef.current
      return lastOperationSucceededRef.current
    }
    if (maxWaitMs === undefined) return wait()
    let timeoutId: ReturnType<typeof setTimeout> | undefined
    try {
      return await Promise.race([
        wait(),
        new Promise<boolean>(resolve => {
          timeoutId = setTimeout(() => resolve(false), Math.max(0, maxWaitMs))
        }),
      ])
    } finally {
      if (timeoutId !== undefined) clearTimeout(timeoutId)
    }
  }, [])

  const readFiles = useCallback(async (): Promise<File[]> => {
    try {
      if (refsRef.current.length !== filesRef.current.length) throw new Error('ASSET_CONTENT_MISSING')
      return await mapPhotoIo(filesRef.current, async file => {
        if (file.status === 'error' || !file.uid) throw new Error('ASSET_CONTENT_MISSING')
        const response = await axios.get<Blob>(API_ENDPOINTS.WORKBENCH_CASE_ASSET(caseId, file.uid), { responseType: 'blob' })
        return new File([response.data], file.name, { type: file.type || 'image/jpeg' })
      })
    } catch (error) {
      setAssetError(errorMessage(error))
      throw error
    }
  }, [caseId])

  return {
    files, assetError, uploading, navigationUnsafe: uploading || bindingSaveFailed,
    handleChange, readFiles, waitForIdle,
  }
}
