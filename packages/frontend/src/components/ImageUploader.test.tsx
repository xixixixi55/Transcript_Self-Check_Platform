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
    Button: ({ children, icon, onClick }: { children: React.ReactNode; icon?: React.ReactNode; onClick?: () => void }) => (
      <button onClick={onClick}>{icon}{children}</button>
    ),
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
  it('通过独立按钮批量选择，并按多段数字和扩展名自然排序后一次填入', () => {
    const onChange = vi.fn()
    const view = render(<ImageUploader materials={materials} photos={[]} onChange={onChange} />)
    const input = view.container.querySelector('input[type="file"][multiple]') as HTMLInputElement
    const files = [
      new File(['4'], 'case10_pic1.png', { type: 'image/png' }),
      new File(['3'], 'case2_pic10.png', { type: 'image/png' }),
      new File(['2'], 'case2_pic2.png', { type: 'image/png' }),
      new File(['1'], 'case2_pic2.jpg', { type: 'image/jpeg' }),
    ]

    expect(screen.getByRole('button', { name: '批量导入图片' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '检材 1 · SYN-JC00000001 图片 1 添加' })).toBeTruthy()
    fireEvent.change(input, { target: { files } })

    expect(onChange).toHaveBeenCalledOnce()
    expect(onChange.mock.calls[0][0].map((file: UploadFile) => file.name)).toEqual([
      'case2_pic2.jpg', 'case2_pic2.png', 'case2_pic10.png', 'case10_pic1.png',
    ])
    expect(onChange.mock.calls[0][0].every((file: UploadFile) => file.originFileObj)).toBe(true)
  })

  it('按检材位置-图片位置识别三组图片且不依赖检材编号', () => {
    const threeMaterials: EvidenceItem[] = [...materials, {
      id: 'material-synthetic-3', evidence_number: 'SYN-JC00990003',
      device_type: '', device_name: '', model: '',
    }]
    const files = [
      new File(['6'], '003-2.JPG', { type: 'image/jpeg' }),
      new File(['2'], '1-2.png', { type: 'image/png' }),
      new File(['3'], '2-1.png', { type: 'image/png' }),
      new File(['1'], '1-1.jpg', { type: 'image/jpeg' }),
      new File(['5'], '3-1.jpeg', { type: 'image/jpeg' }),
      new File(['4'], '2-2.png', { type: 'image/png' }),
    ]
    const onChange = vi.fn()
    const view = render(<ImageUploader materials={threeMaterials} photos={[]} onChange={onChange} />)

    fireEvent.change(view.container.querySelector('input[type="file"][multiple]') as HTMLInputElement, { target: { files } })

    expect(onChange).toHaveBeenCalledOnce()
    expect(onChange.mock.calls[0][0].map((file: UploadFile) => file.name)).toEqual([
      '1-1.jpg', '1-2.png', '2-1.png', '2-2.png', '3-1.jpeg', '003-2.JPG',
    ])
  })

  it('分组命名出现重复槽位时整批拒绝', () => {
    vi.mocked(message.error).mockClear()
    const onChange = vi.fn()
    const view = render(<ImageUploader materials={materials} photos={[]} onChange={onChange} />)
    const files = [
      new File(['1'], '1-1.png', { type: 'image/png' }),
      new File(['2'], '1-1.jpg', { type: 'image/jpeg' }),
      new File(['3'], '2-1.png', { type: 'image/png' }),
      new File(['4'], '2-2.png', { type: 'image/png' }),
    ]

    fireEvent.change(view.container.querySelector('input[type="file"][multiple]') as HTMLInputElement, { target: { files } })

    expect(onChange).not.toHaveBeenCalled()
    expect(message.error).toHaveBeenCalledWith(
      '按“检材顺序-图片顺序”命名时，每个检材都应各有 1、2 两张图片（如 1-1、1-2），未导入任何图片。',
    )
  })

  it.each([
    ['检材位置越界', ['1-1.png', '1-2.png', '3-1.png', '3-2.png']],
    ['图片位置非法', ['1-1.png', '1-3.png', '2-1.png', '2-2.png']],
  ])('分组命名%s时整批拒绝', (_caseName, names) => {
    vi.mocked(message.error).mockClear()
    const onChange = vi.fn()
    const view = render(<ImageUploader materials={materials} photos={[]} onChange={onChange} />)
    const files = names.map(name => new File(['SYNTHETIC'], name, { type: 'image/png' }))

    fireEvent.change(view.container.querySelector('input[type="file"][multiple]') as HTMLInputElement, { target: { files } })

    expect(onChange).not.toHaveBeenCalled()
    expect(message.error).toHaveBeenCalledWith(
      '按“检材顺序-图片顺序”命名时，每个检材都应各有 1、2 两张图片（如 1-1、1-2），未导入任何图片。',
    )
  })

  it('分组命名与普通自然排序命名混用时整批拒绝', () => {
    vi.mocked(message.error).mockClear()
    const onChange = vi.fn()
    const view = render(<ImageUploader materials={materials} photos={[]} onChange={onChange} />)
    const files = [
      new File(['1'], '1-1.png', { type: 'image/png' }),
      new File(['2'], '1-2.png', { type: 'image/png' }),
      new File(['3'], 'pic1003.png', { type: 'image/png' }),
      new File(['4'], 'pic1005.png', { type: 'image/png' }),
    ]

    fireEvent.change(view.container.querySelector('input[type="file"][multiple]') as HTMLInputElement, { target: { files } })

    expect(onChange).not.toHaveBeenCalled()
    expect(message.error).toHaveBeenCalledWith(
      '请统一使用“检材顺序-图片顺序”（如 1-1、1-2）或普通数字文件名，未导入任何图片。',
    )
  })

  it('批量数量不匹配时整批拒绝并保留既有图片', () => {
    vi.mocked(message.error).mockClear()
    const onChange = vi.fn()
    const existing = [photo(1), photo(2)]
    const view = render(<ImageUploader materials={materials} photos={existing} onChange={onChange} />)
    const input = view.container.querySelector('input[type="file"][multiple]') as HTMLInputElement

    fireEvent.change(input, { target: { files: [
      new File(['1'], 'pic1001.png', { type: 'image/png' }),
      new File(['2'], 'pic1002.png', { type: 'image/png' }),
      new File(['3'], 'front.gif', { type: 'image/gif' }),
    ] } })

    expect(onChange).not.toHaveBeenCalled()
    expect(message.error).toHaveBeenCalledWith(
      '当前有 2 个检材，应选择 4 张图片；本次选择 3 张，未导入任何图片。',
    )
    expect(screen.getByText('SYNTHETIC-photo-1.png')).toBeTruthy()
    expect(screen.getByText('SYNTHETIC-photo-2.png')).toBeTruthy()
  })

  it('批量图片存在无数字文件名时整批拒绝', () => {
    vi.mocked(message.error).mockClear()
    const onChange = vi.fn()
    const view = render(<ImageUploader materials={materials.slice(0, 1)} photos={[]} onChange={onChange} />)
    const input = view.container.querySelector('input[type="file"][multiple]') as HTMLInputElement

    fireEvent.change(input, { target: { files: [
      new File(['a'], 'front.png', { type: 'image/png' }),
      new File(['2'], 'pic1002.png', { type: 'image/png' }),
    ] } })

    expect(onChange).not.toHaveBeenCalled()
    expect(message.error).toHaveBeenCalledWith('front.png：文件名必须包含数字，未导入任何图片。')
  })

  it('一次处理 202 张图片并按顺序对应 101 个检材', () => {
    const manyMaterials = Array.from({ length: 101 }, (_, index): EvidenceItem => ({
      id: `material-synthetic-${index + 1}`,
      evidence_number: `SYN-JC${String(index + 1).padStart(8, '0')}`,
      device_type: '', device_name: '', model: '',
    }))
    const files = Array.from({ length: 202 }, (_, index) => new File(
      ['SYNTHETIC'], `pic${202 - index}.png`, { type: 'image/png' },
    ))
    const onChange = vi.fn()
    const view = render(<ImageUploader materials={manyMaterials} photos={[]} onChange={onChange} />)

    fireEvent.change(view.container.querySelector('input[type="file"][multiple]') as HTMLInputElement, { target: { files } })

    expect(onChange).toHaveBeenCalledOnce()
    const imported = onChange.mock.calls[0][0] as UploadFile[]
    expect(imported).toHaveLength(202)
    expect(imported.slice(0, 2).map(file => file.name)).toEqual(['pic1.png', 'pic2.png'])
    expect(imported.slice(-2).map(file => file.name)).toEqual(['pic201.png', 'pic202.png'])
  })

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
