import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { message } from 'antd'
import type { UploadFile } from 'antd'
import { MAX_IMAGE_SIZE } from '@biji/shared/constants'
import type { EvidenceItem } from '@biji/shared/types'
import ImageUploader from './ImageUploader'

vi.mock('antd', () => {
  const UploadMock = ({ children, fileList, onChange, beforeUpload, 'aria-label': ariaLabel }: {
    children?: React.ReactNode
    fileList: UploadFile[]
    onChange: (info: { fileList: UploadFile[] }) => void
    beforeUpload?: (file: File) => unknown
    'aria-label'?: string
  }) => (
    <div aria-label={ariaLabel}>
      {fileList.map(file => (
        <div key={file.uid}>
          <span>{file.name}</span>
          <button aria-label={`删除 ${file.name}`} onClick={() => onChange({ fileList: [] })}>删除</button>
        </div>
      ))}
      {children && (
        <>
          <button aria-label={`${ariaLabel} 添加`} onClick={() => onChange({
            fileList: [{ uid: `new-${ariaLabel}`, name: `SYNTHETIC-${ariaLabel}.png` }],
          })}>{children}</button>
          <button aria-label={`${ariaLabel} 校验100MB`} onClick={() => beforeUpload?.({
            name: 'SYNTHETIC-boundary.png', size: 100 * 1024 * 1024,
          } as File)}>校验100MB</button>
          <button aria-label={`${ariaLabel} 校验超限`} onClick={() => beforeUpload?.({
            name: 'SYNTHETIC-too-large.png', size: 100 * 1024 * 1024 + 1,
          } as File)}>校验超限</button>
        </>
      )}
    </div>
  )
  return {
    Upload: Object.assign(UploadMock, { LIST_IGNORE: 'LIST_IGNORE' }),
    message: { error: vi.fn() },
  }
})

vi.mock('@ant-design/icons', () => ({ UploadOutlined: () => null }))

const materials: EvidenceItem[] = [
  { id: 'material-synthetic-1', evidence_number: 'SYN-JC00000001', device_type: '', device_name: '', model: '' },
  { id: 'material-synthetic-2', evidence_number: 'SYN-JC00000002', device_type: '', device_name: '', model: '' },
]

function photo(index: number): UploadFile {
  return { uid: `photo-synthetic-${index}`, name: `SYNTHETIC-photo-${index}.png`, status: 'done' }
}

describe('ImageUploader material groups', () => {
  it('允许恰好 100MB 的图片并拒绝超过 100MB 的图片', () => {
    vi.mocked(message.error).mockClear()
    render(<ImageUploader materials={materials.slice(0, 1)} photos={[]} onChange={vi.fn()} />)

    expect(MAX_IMAGE_SIZE).toBe(100 * 1024 * 1024)
    fireEvent.click(screen.getByRole('button', { name: '检材 1 · SYN-JC00000001 图片 1 校验100MB' }))
    expect(message.error).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: '检材 1 · SYN-JC00000001 图片 1 校验超限' }))
    expect(message.error).toHaveBeenCalledWith('图片不能超过 100MB')
  })

  it('按检材顺序展示双图片槽位，并只开放下一个空槽', () => {
    render(<ImageUploader materials={materials} photos={[photo(1), photo(2), photo(3)]} onChange={vi.fn()} />)

    expect(screen.getByText('检材 1 · SYN-JC00000001')).toBeTruthy()
    expect(screen.getByText('检材 2 · SYN-JC00000002')).toBeTruthy()
    expect(screen.getAllByText('图片 1')).toHaveLength(2)
    expect(screen.getAllByText('图片 2')).toHaveLength(2)
    expect(screen.getByRole('button', { name: '检材 2 · SYN-JC00000002 图片 2 添加' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: '检材 1 · SYN-JC00000001 图片 1 添加' })).toBeNull()
    expect(screen.queryByText('按顺序等待上传')).toBeNull()
  })

  it('为尚未轮到上传的后续槽位显示不可点击占位框', () => {
    render(<ImageUploader materials={materials} photos={[]} onChange={vi.fn()} />)

    expect(screen.getAllByText('按顺序等待上传')).toHaveLength(3)
    expect(screen.getByRole('button', { name: '检材 1 · SYN-JC00000001 图片 1 添加' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: '检材 1 · SYN-JC00000001 图片 2 添加' })).toBeNull()
  })

  it('从下一个空槽添加图片时保持扁平有序列表', () => {
    const onChange = vi.fn()
    const existing = [photo(1), photo(2)]
    render(<ImageUploader materials={materials} photos={existing} onChange={onChange} />)

    fireEvent.click(screen.getByRole('button', { name: '检材 2 · SYN-JC00000002 图片 1 添加' }))
    expect(onChange).toHaveBeenCalledWith([
      ...existing,
      expect.objectContaining({ uid: 'new-检材 2 · SYN-JC00000002 图片 1' }),
    ])
  })

  it('删除前序图片时让后续图片按既有顺序前移', () => {
    const onChange = vi.fn()
    const photos = [photo(1), photo(2), photo(3)]
    render(<ImageUploader materials={materials} photos={photos} onChange={onChange} />)

    fireEvent.click(screen.getByRole('button', { name: '删除 SYNTHETIC-photo-1.png' }))
    expect(onChange).toHaveBeenCalledWith([photos[1], photos[2]])
  })

  it('显示并允许删除超出当前检材容量的待处理图片', () => {
    const onChange = vi.fn()
    const photos = [photo(1), photo(2), photo(3)]
    render(<ImageUploader materials={materials.slice(0, 1)} photos={photos} onChange={onChange} />)

    expect(screen.getByText('待处理图片')).toBeTruthy()
    expect(screen.getByText('当前图片多于检材可对应数量，请删除多余图片或先补充检材。')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '删除 SYNTHETIC-photo-3.png' }))
    expect(onChange).toHaveBeenCalledWith([photos[0], photos[1]])
  })

  it('没有检材时提示先添加检材且不开放上传入口', () => {
    render(<ImageUploader materials={[]} photos={[]} onChange={vi.fn()} />)

    expect(screen.getByText('请先在“检材情况”中添加检材，再上传对应图片。')).toBeTruthy()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('检材被删空后仍显示并允许删除全部待处理图片', () => {
    const onChange = vi.fn()
    const photos = [photo(1), photo(2)]
    render(<ImageUploader materials={[]} photos={photos} onChange={onChange} />)

    expect(screen.getByText('待处理图片')).toBeTruthy()
    expect(screen.getByText('SYNTHETIC-photo-1.png')).toBeTruthy()
    expect(screen.getByText('SYNTHETIC-photo-2.png')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '删除 SYNTHETIC-photo-1.png' }))
    expect(onChange).toHaveBeenCalledWith([photos[1]])
  })
})
