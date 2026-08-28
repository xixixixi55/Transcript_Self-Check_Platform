// 第 11 层：FE_Components — 附件图片上传组件
import React, { useState } from 'react'
import { Button, Tooltip, Upload } from 'antd'
import { DownOutlined, UpOutlined, UploadOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd'
import { SUPPORTED_IMAGE_FORMATS } from '@biji/shared/constants'
import type { EvidenceItem } from '@biji/shared/types'
import { useBatchImageImport } from '../hooks/useBatchImageImport'

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
  const [expanded, setExpanded] = useState(true)
  const { inputRef, beforeUpload, importBatch, openBatchPicker } = useBatchImageImport({
    materialCount: materials.length, onChange,
  })
  const updateSlot = (slotIndex: number, fileList: UploadFile[]) => {
    if (fileList.length) {
      const next = [...photos]
      next.splice(slotIndex, photos[slotIndex] ? 1 : 0, fileList[fileList.length - 1])
      onChange(next)
      return
    }
    onChange(photos.filter((_, index) => index !== slotIndex))
  }

  const capacity = materials.length * 2
  const nextEmptySlot = capacity > 0 ? Math.min(photos.length, capacity - 1) : -1
  const overflowPhotos = photos.slice(capacity)
  const toggleLabel = expanded ? '收起图片' : '展开图片'

  return (
    <div className="material-photo-uploader">
      {materials.length ? <>
        <div className="material-photo-uploader__header">
          {expanded && <p className="material-photo-uploader__hint">
            每个检材对应两张图片；支持普通数字自然排序，或用 1-1、1-2 表示第一个检材的两张图片。
          </p>}
          <input
            ref={inputRef}
            type="file"
            accept={SUPPORTED_IMAGE_FORMATS.join(',')}
            multiple
            hidden
            aria-label="批量导入图片"
            onChange={importBatch}
          />
          <div className="material-photo-uploader__actions">
            {expanded && <Tooltip title="批量导入图片">
              <Button type="text" size="small" shape="circle" icon={<UploadOutlined />}
                aria-label="批量导入图片" onClick={openBatchPicker} />
            </Tooltip>}
            <Tooltip title={toggleLabel}>
              <Button type="text" size="small" shape="circle"
                icon={expanded ? <UpOutlined /> : <DownOutlined />}
                aria-label={toggleLabel}
                aria-expanded={expanded}
                aria-controls="material-photo-content"
                onClick={() => setExpanded(value => !value)} />
            </Tooltip>
          </div>
        </div>
        {expanded ? <div id="material-photo-content" className="material-photo-uploader__groups">
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
        </div> : <div id="material-photo-content" className="material-photo-summary" role="list">
          {materials.map((material, materialIndex) => {
            const filledCount = Math.min(2, Math.max(0, photos.length - materialIndex * 2))
            return (
              <div className="material-photo-summary__item" role="listitem"
                key={material.evidence_id || material.id || materialIndex}>
                <span>{materialLabel(material, materialIndex)}</span>
                <span className={`material-photo-summary__count${filledCount === 2 ? ' material-photo-summary__count--complete' : ''}`}>
                  {filledCount}/2
                </span>
              </div>
            )
          })}
        </div>}
      </> : (
        <div className="material-photo-uploader__empty">
          请先在“检材情况”中添加检材，再上传对应图片。
        </div>
      )}
      {expanded && overflowPhotos.length > 0 && (
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
