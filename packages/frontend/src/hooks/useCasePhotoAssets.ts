// Layer 10: FE_Hooks — persistent case-bound photo upload and recovery.
import { useCallback, useEffect, useRef, useState } from 'react'
import axios from 'axios'
import { API_ENDPOINTS } from '@biji/shared/constants'
import type { CaseAssetList, CaseAssetRecord, EditLease, OpaqueAssetRef } from '@biji/shared/types'
import type { UploadFile } from 'antd'

interface Options {
  caseId: string
  assetRefs: OpaqueAssetRef[]
  editingEnabled: boolean
  lease: EditLease | null
  onAssetRefsChange: (refs: OpaqueAssetRef[]) => boolean
}

function errorMessage(error: any): string {
  const code = error?.response?.data?.detail?.code || error?.message
  return code === 'ASSET_CONTENT_MISSING'
    ? '图片资产缺失，请重新上传。'
    : code === 'ASSET_CONTENT_CORRUPT'
      ? '图片资产已损坏，请重新上传。'
      : code === 'LEASE_NOT_ACTIVE' || code === 'LEASE_EXPIRED'
        ? '编辑租约已失效，图片修改未保存。'
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

export function useCasePhotoAssets(options: Options) {
  const { caseId, assetRefs, editingEnabled, lease, onAssetRefsChange } = options
  const [files, setFiles] = useState<UploadFile[]>([])
  const [assetError, setAssetError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const uploadingRef = useRef(false)
  const requestSequence = useRef(0)
  const filesRef = useRef<UploadFile[]>([])
  const refsRef = useRef(assetRefs)
  const refsKey = assetRefs.map(ref => `${ref.asset_id}:${ref.fingerprint || ''}`).join('|')

  useEffect(() => { refsRef.current = assetRefs }, [assetRefs])
  useEffect(() => { filesRef.current = files }, [files])

  useEffect(() => {
    const sequence = ++requestSequence.current
    let active = true
    setFiles([])
    setAssetError(null)
    axios.get<{ data: CaseAssetList }>(API_ENDPOINTS.WORKBENCH_CASE_ASSETS(caseId))
      .then(response => {
        if (!active || sequence !== requestSequence.current) return
        const records = new Map(response.data.data.items.map(item => [item.asset_id, item]))
        const restored = assetRefs.map(ref => {
          const record = records.get(ref.asset_id)
          const available = record?.content_status === 'available'
          return {
            uid: ref.asset_id, name: fileName(ref), type: fileType(ref), status: available ? 'done' : 'error',
            url: API_ENDPOINTS.WORKBENCH_CASE_ASSET(caseId, ref.asset_id),
          } as UploadFile
        })
        if (restored.some(file => file.status === 'error')) setAssetError('部分图片资产无法读取，请重新上传后再导出。')
        setFiles(restored)
      })
      .catch(error => {
        if (active && sequence === requestSequence.current) setAssetError(errorMessage(error))
      })
    return () => { active = false }
  }, [caseId, refsKey]) // refsKey changes only when the persisted asset set changes.

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

  const handleChange = useCallback(async (nextFiles: UploadFile[]) => {
    if (!editingEnabled || uploadingRef.current) return
    const newFiles = nextFiles.filter(file => file.originFileObj && !refsRef.current.some(ref => ref.asset_id === file.uid))
    if (!newFiles.length) {
      filesRef.current = nextFiles
      setFiles(nextFiles)
      const nextRefs = nextFiles.flatMap(file => refsRef.current.filter(ref => ref.asset_id === file.uid))
      if (JSON.stringify(nextRefs) !== JSON.stringify(refsRef.current)) {
        refsRef.current = nextRefs
        onAssetRefsChange(nextRefs)
      }
      return
    }
    uploadingRef.current = true
    setUploading(true)
    setAssetError(null)
    setFiles(nextFiles.map(file => newFiles.some(item => item.uid === file.uid) ? { ...file, status: 'uploading' } : file))
    try {
      const uploaded = await Promise.all(newFiles.map(async file => [file.uid, await upload(file)] as const))
      const uploadedByUid = new Map(uploaded)
      const nextRefs = nextFiles.flatMap(file => {
        const created = uploadedByUid.get(file.uid)
        if (created) return [refForRecord(created)]
        return refsRef.current.filter(ref => ref.asset_id === file.uid)
      })
      const restored = nextFiles.map(file => {
        const created = uploadedByUid.get(file.uid)
        return created ? { uid: created.asset_id, name: fileName(created), type: fileType(created), status: 'done', url: API_ENDPOINTS.WORKBENCH_CASE_ASSET(caseId, created.asset_id) } as UploadFile : file
      })
      refsRef.current = nextRefs
      filesRef.current = restored
      setFiles(restored)
      onAssetRefsChange(nextRefs)
    } catch (error) {
      setFiles(filesRef.current)
      setAssetError(errorMessage(error))
    } finally {
      uploadingRef.current = false
      setUploading(false)
    }
  }, [caseId, editingEnabled, onAssetRefsChange, upload])

  const readFiles = useCallback(async (): Promise<File[]> => {
    try {
      if (refsRef.current.length !== filesRef.current.length) throw new Error('ASSET_CONTENT_MISSING')
      return await Promise.all(filesRef.current.map(async file => {
        if (file.status === 'error' || !file.uid) throw new Error('ASSET_CONTENT_MISSING')
        const response = await axios.get<Blob>(API_ENDPOINTS.WORKBENCH_CASE_ASSET(caseId, file.uid), { responseType: 'blob' })
        return new File([response.data], file.name, { type: file.type || 'image/jpeg' })
      }))
    } catch (error) {
      setAssetError(errorMessage(error))
      throw error
    }
  }, [caseId])

  return { files, assetError, uploading, handleChange, readFiles }
}
