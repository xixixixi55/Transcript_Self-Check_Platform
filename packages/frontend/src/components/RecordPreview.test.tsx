// T030: Component test — verify component exports (REQ-007)
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
})
