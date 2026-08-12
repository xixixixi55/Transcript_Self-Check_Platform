// T030: Component test — verify component exports (REQ-007)
import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'

// Mock antd to avoid slow imports in test
vi.mock('antd', () => ({
  Upload: () => null,
  Button: () => null,
  Card: () => null,
  Form: Object.assign(() => null, { Item: () => null }),
  Input: Object.assign(() => null, { TextArea: () => null }),
  Table: () => null,
  Modal: () => null,
  Select: () => null,
  message: { success: vi.fn(), error: vi.fn() },
  Popconfirm: () => null,
  Space: () => null,
  Steps: Object.assign(() => null, { Step: () => null }),
  Typography: { Title: () => null, Text: () => null, Paragraph: () => null },
  Divider: () => null,
  Alert: () => null,
  Spin: () => null,
  Image: () => null,
  Menu: () => null,
  Layout: Object.assign(() => null, { Header: () => null, Content: () => null, Footer: () => null }),
}))

vi.mock('@ant-design/icons', () => ({
  UploadOutlined: () => null,
  FolderOpenOutlined: () => null,
  FileTextOutlined: () => null,
  DownloadOutlined: () => null,
  PlusOutlined: () => null,
  DeleteOutlined: () => null,
  EditOutlined: () => null,
  EyeOutlined: () => null,
  HomeOutlined: () => null,
  SettingOutlined: () => null,
}))

describe('ReportUploader', () => {
  it('should export a default function', async () => {
    const mod = await import('./ReportUploader')
    expect(typeof mod.default).toBe('function')
  }, 1000)
})

describe('EvidenceEditor', () => {
  it('should export a default function', async () => {
    const mod = await import('./EvidenceEditor')
    expect(typeof mod.default).toBe('function')
  }, 1000)
})

describe('InspectorEditor', () => {
  it('should export a default function', async () => {
    const mod = await import('./InspectorEditor')
    expect(typeof mod.default).toBe('function')
  }, 1000)
})

describe('ImageUploader', () => {
  it('should export a default function', async () => {
    const mod = await import('./ImageUploader')
    expect(typeof mod.default).toBe('function')
  }, 1000)

  it('说明图片按照检材顺序每两张对应一个检材', async () => {
    const { default: ImageUploader } = await import('./ImageUploader')
    render(<ImageUploader materials={[{
      id: 'material-synthetic', evidence_number: 'SYN-JC00000001', device_type: '', device_name: '', model: '',
    }]} photos={[]} onChange={vi.fn()} />)

    expect(screen.getByText('每个检材对应两张图片，按检材顺序依次对应。')).toBeTruthy()
    expect(screen.queryByText(/照片数量必须为偶数/)).toBeNull()
  }, 1000)
})
