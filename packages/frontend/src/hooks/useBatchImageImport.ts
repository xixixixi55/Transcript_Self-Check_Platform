// 第 10 层：FE_Hooks — 原子化的批量图片选择与排序。
import { useCallback, useRef } from 'react'
import type { ChangeEvent } from 'react'
import { message, Upload } from 'antd'
import type { UploadFile } from 'antd'
import { MAX_IMAGE_SIZE, SUPPORTED_IMAGE_FORMATS } from '@biji/shared/constants'
import {
  hasNumericFileName,
  parseMaterialPhotoPosition,
  sortFilesByNumericName,
} from '@biji/shared/utils'

interface Options {
  materialCount: number
  onChange: (files: UploadFile[]) => void
}

function imageValidationError(file: File): string | null {
  const ext = '.' + file.name.split('.').pop()?.toLowerCase()
  if (!SUPPORTED_IMAGE_FORMATS.includes(ext)) return '仅支持 JPG/PNG 格式'
  if (file.size > MAX_IMAGE_SIZE) return '图片不能超过 100MB'
  return null
}

function orderBatchFiles(files: File[], materialCount: number): File[] | null {
  const positioned = files.map(file => ({
    file,
    position: parseMaterialPhotoPosition(file.name),
  }))
  const positionedCount = positioned.filter(item => item.position).length
  if (!positionedCount) return sortFilesByNumericName(files)
  if (positionedCount !== files.length) {
    message.error('请统一使用“检材顺序-图片顺序”（如 1-1、1-2）或普通数字文件名，未导入任何图片。')
    return null
  }
  const keys = new Set(positioned.map(item => (
    `${item.position?.materialPosition}-${item.position?.photoPosition}`
  )))
  const positionsValid = positioned.every(({ position }) => (
    position
    && Number.isSafeInteger(position.materialPosition)
    && position.materialPosition >= 1
    && position.materialPosition <= materialCount
    && (position.photoPosition === 1 || position.photoPosition === 2)
  ))
  if (!positionsValid || keys.size !== files.length) {
    message.error('按“检材顺序-图片顺序”命名时，每个检材都应各有 1、2 两张图片（如 1-1、1-2），未导入任何图片。')
    return null
  }
  return positioned
    .sort((left, right) => (
      left.position!.materialPosition - right.position!.materialPosition
      || left.position!.photoPosition - right.position!.photoPosition
    ))
    .map(item => item.file)
}

export function useBatchImageImport({ materialCount, onChange }: Options) {
  const inputRef = useRef<HTMLInputElement>(null)
  const beforeUpload = useCallback((file: File) => {
    const validationError = imageValidationError(file)
    if (validationError) {
      message.error(validationError)
      return Upload.LIST_IGNORE
    }
    return false
  }, [])
  const importBatch = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(event.currentTarget.files || [])
    event.currentTarget.value = ''
    if (!selectedFiles.length) return
    const expectedCount = materialCount * 2
    if (selectedFiles.length !== expectedCount) {
      message.error(`当前有 ${materialCount} 个检材，应选择 ${expectedCount} 张图片；本次选择 ${selectedFiles.length} 张，未导入任何图片。`)
      return
    }
    const invalidFile = selectedFiles.find(file => imageValidationError(file))
    if (invalidFile) {
      message.error(`${invalidFile.name}：${imageValidationError(invalidFile)}，未导入任何图片。`)
      return
    }
    const unnamedFile = selectedFiles.find(file => !hasNumericFileName(file.name))
    if (unnamedFile) {
      message.error(`${unnamedFile.name}：文件名必须包含数字，未导入任何图片。`)
      return
    }
    const orderedFiles = orderBatchFiles(selectedFiles, materialCount)
    if (!orderedFiles) return
    onChange(orderedFiles.map((file, index) => ({
      uid: `batch-${file.lastModified}-${file.size}-${index}-${file.name}`,
      name: file.name,
      type: file.type,
      originFileObj: file as unknown as NonNullable<UploadFile['originFileObj']>,
    })))
  }, [materialCount, onChange])
  const openBatchPicker = useCallback(() => inputRef.current?.click(), [])
  return { inputRef, beforeUpload, importBatch, openBatchPicker }
}
