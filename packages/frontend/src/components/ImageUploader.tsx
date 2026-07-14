// Layer 11: FE_Components — 附件图片上传组件
import React from 'react'
import { Upload, Button, Image, Space, message } from 'antd'
import { UploadOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd'
import { SUPPORTED_IMAGE_FORMATS, MAX_IMAGE_SIZE } from '@biji/shared/constants'

interface Props {
  photos: UploadFile[]
  onChange: (photos: UploadFile[]) => void
}

export default function ImageUploader({ photos, onChange }: Props) {
  const handleChange: any = (info: { fileList: UploadFile[] }) => {
    onChange(info.fileList)
  }

  const beforeUpload = (file: File) => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!SUPPORTED_IMAGE_FORMATS.includes(ext)) {
      message.error('仅支持 JPG/PNG 格式')
      return Upload.LIST_IGNORE
    }
    if (file.size > MAX_IMAGE_SIZE) {
      message.error('图片不能超过 10MB')
      return Upload.LIST_IGNORE
    }
    return false // 阻止自动上传，手动管理
  }

  return (
    <div>
      <Upload
        listType="picture-card"
        fileList={photos}
        onChange={handleChange}
        beforeUpload={beforeUpload}
        multiple
      >
        {photos.length < 10 && <div><UploadOutlined /><div style={{ marginTop: 8 }}>上传照片</div></div>}
      </Upload>
      <p style={{ color: '#999', fontSize: 13, marginTop: 8 }}>
        支持 .jpg / .png，单张不超过 10MB，最多 10 张。可拖拽排序。
      </p>
    </div>
  )
}
