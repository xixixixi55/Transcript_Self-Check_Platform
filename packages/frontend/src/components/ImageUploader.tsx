// Layer 11: FE_Components — 附件图片上传组件
import React from 'react'
import { Upload, message } from 'antd'
import { UploadOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd'
import { SUPPORTED_IMAGE_FORMATS, MAX_IMAGE_SIZE } from '@biji/shared/constants'
import type { EvidenceItem } from '@biji/shared/types'

interface Props {
  materials: EvidenceItem[]
  photos: UploadFile[]
  onChange: (photos: UploadFile[]) => void
}

function materialLabel(material: EvidenceItem, index: number): string {
  const number = material.evidence_number?.trim()
  return number ? `检材 ${index + 1} · ${number}` : `检材 ${index + 1} · 编号待填写`
}

export default function ImageUploader({ materials, photos, onChange }: Props) {
  const updateSlot = (slotIndex: number, fileList: UploadFile[]) => {
    if (fileList.length) {
      const next = [...photos]
      next.splice(slotIndex, photos[slotIndex] ? 1 : 0, fileList[fileList.length - 1])
      onChange(next)
      return
    }
    onChange(photos.filter((_, index) => index !== slotIndex))
  }

  const beforeUpload = (file: File) => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!SUPPORTED_IMAGE_FORMATS.includes(ext)) {
      message.error('仅支持 JPG/PNG 格式')
      return Upload.LIST_IGNORE
    }
    if (file.size > MAX_IMAGE_SIZE) {
      message.error('图片不能超过 100MB')
      return Upload.LIST_IGNORE
    }
    return false // 阻止自动上传，手动管理
  }

  const capacity = materials.length * 2
  const nextEmptySlot = capacity > 0 ? Math.min(photos.length, capacity - 1) : -1
  const overflowPhotos = photos.slice(capacity)

  return (
    <div className="material-photo-uploader">
      {materials.length ? <>
        <p className="material-photo-uploader__hint">每个检材对应两张图片，按检材顺序依次对应。</p>
        <div className="material-photo-uploader__groups">
          {materials.map((material, materialIndex) => (
          <section className="material-photo-group" key={material.evidence_id || material.id || materialIndex}>
            <div className="material-photo-group__title">{materialLabel(material, materialIndex)}</div>
            <div className="material-photo-group__slots">
              {[0, 1].map(photoIndex => {
                const slotIndex = materialIndex * 2 + photoIndex
                const file = photos[slotIndex]
                const canUpload = !file && slotIndex === nextEmptySlot && photos.length < capacity
                return (
                  <div className="material-photo-slot" key={slotIndex}>
                    <div className="material-photo-slot__label">图片 {photoIndex + 1}</div>
                    {file || canUpload ? (
                      <Upload
                        aria-label={`${materialLabel(material, materialIndex)} 图片 ${photoIndex + 1}`}
                        listType="picture-card"
                        fileList={file ? [file] : []}
                        onChange={info => updateSlot(slotIndex, info.fileList)}
                        beforeUpload={beforeUpload}
                        maxCount={1}
                      >
                        {canUpload ? <div><UploadOutlined /><div>添加图片</div></div> : null}
                      </Upload>
                    ) : (
                      <div className="material-photo-slot__waiting">按顺序等待上传</div>
                    )}
                  </div>
                )
              })}
            </div>
          </section>
          ))}
        </div>
      </> : (
        <div className="material-photo-uploader__empty">
          请先在“检材情况”中添加检材，再上传对应图片。
        </div>
      )}
      {overflowPhotos.length > 0 && (
        <section className="material-photo-overflow">
          <div className="material-photo-overflow__title">待处理图片</div>
          <p>当前图片多于检材可对应数量，请删除多余图片或先补充检材。</p>
          <div className="material-photo-overflow__list">
            {overflowPhotos.map((file, index) => (
              <Upload key={file.uid} listType="picture-card" fileList={[file]}
                onChange={info => updateSlot(capacity + index, info.fileList)}
                beforeUpload={beforeUpload} maxCount={1} />
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
