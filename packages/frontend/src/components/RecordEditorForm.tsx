// Layer 11: FE_Components — 笔录审核编辑表单
// 从 RecordGeneratePage 提取，解决页面文件大小超标
import React from 'react'
import { Button, Checkbox, Input, Space, Steps, Typography, Divider, Alert } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import type { InspectionReport } from '@biji/shared/types'
import type { UploadFile } from 'antd'
import EditableField from './EditableField'
import EvidenceEditor from './EvidenceEditor'
import InspectorEditor from './InspectorEditor'
import ProcessStepsEditor from './ProcessStepsEditor'
import SoftwareToolsList from './SoftwareToolsList'
import ExtractListEditor from './ExtractListEditor'
import ImageUploader from './ImageUploader'
import { DateTimeField } from './DateTimeField'
import { normalizeDataSummary } from '@biji/shared/utils'

const { Title, Text } = Typography

interface Props {
  report: InspectionReport
  updateReport: (path: string, value: any) => void
  onExport: () => void
  exporting: boolean
  onBackToUpload: () => void
  deviceOptions: { label: string; value: string }[]
  photoFiles: UploadFile[]
  onPhotoFilesChange: (files: UploadFile[]) => void
  exportFileName: string
  customFileName: boolean
  exportFileNameError?: string
  onCustomFileNameChange: (enabled: boolean) => void
  onExportFileNameChange: (value: string) => void
}

export default function RecordEditorForm(props: Props) {
  const {
    report, updateReport, onExport, exporting, onBackToUpload, deviceOptions, photoFiles, onPhotoFilesChange,
    exportFileName, customFileName, exportFileNameError, onCustomFileNameChange, onExportFileNameChange,
  } = props
  const intro = report.introduction
  const insp = report.inspection
  const attach = report.attachments || { extract_list: { columns: [], rows: [] }, photo_ids: [], disc_number: '' }

  const sectionLabel: React.CSSProperties = { fontWeight: 600, marginBottom: 4, marginTop: 12 }
  const sectionPad: React.CSSProperties = { padding: '4px 0 12px 0' }

  const resultFields = [
    ['检材编号', 'evidence_number'], ['软件名称', 'software_name'],
    ['软件版本', 'software_version'], ['数据摘要', 'data_summary'],
    ['RAR 文件名', 'rar_filename'], ['MD5 哈希', 'md5_hash'],
    ['文件大小', 'file_size'],
  ]

  return (
    <div style={{ background: '#fff', padding: 32, borderRadius: 8 }}>
      <Title level={2} style={{ textAlign: 'center' }}>{report.title || '电子数据检查笔录'}</Title>

      <div style={sectionLabel}>文号</div>
      <EditableField type="text" value={report.document_number} onChange={v => updateReport('document_number', v)} />
      <Alert message="注意修改文号！" type="warning" showIcon closable style={{ marginTop: 8, marginBottom: 8 }} />

      <div style={sectionLabel}>导出文件名</div>
      <Space direction="vertical" style={{ width: '100%' }} size={4}>
        <Checkbox checked={customFileName} onChange={event => onCustomFileNameChange(event.target.checked)}>
          自定义文件名
        </Checkbox>
        <Input
          aria-label="导出文件名"
          value={exportFileName}
          disabled={!customFileName}
          status={exportFileNameError ? 'error' : undefined}
          onChange={event => onExportFileNameChange(event.target.value)}
          placeholder="请输入不含或包含 .docx 的文件名"
        />
        {exportFileNameError && <Text type="danger">{exportFileNameError}</Text>}
      </Space>

      <Divider>一、绪论</Divider>
      <LabeledField label="（一）委托单位" type="text" value={intro.entrust_unit}
        onChange={v => updateReport('introduction.entrust_unit', v)} />
      <LabeledField label="（二）委 托 人" type="text" value={(intro.entrust_persons || []).join('、')}
        onChange={v => updateReport('introduction.entrust_persons', v.split(/[,，、]/).map(s => s.trim()).filter(Boolean))} />
      <DateTimeField label="（三）委托时间" precision="date" value={intro.entrust_time}
        onChange={v => updateReport('introduction.entrust_time', v)} />
      <LabeledField label="（四）案件简要情况" type="textarea" value={intro.case_summary}
        onChange={v => updateReport('introduction.case_summary', v)} />

      <div style={sectionLabel}>（五）检材情况</div>
      <div style={sectionPad}><EvidenceEditor items={intro.evidence_list || []}
        onChange={v => updateReport('introduction.evidence_list', v)} /></div>

      <LabeledField label="（六）检查要求" type="textarea" value={intro.inspection_requirement}
        onChange={v => updateReport('introduction.inspection_requirement', v)} />
      <DateTimeField label="（七）检查起止时间" precision="minute-range" value={intro.inspection_time_range}
        onChange={v => updateReport('introduction.inspection_time_range', v)} />

      <div style={sectionLabel}>（八）检查人员</div>
      <div style={sectionPad}><InspectorEditor inspectors={intro.inspectors || []}
        onChange={v => updateReport('introduction.inspectors', v)} /></div>

      <LabeledField label="（九）检查地点" type="text" value={intro.inspection_place}
        onChange={v => updateReport('introduction.inspection_place', v)} />

      <Divider>二、检查</Divider>
      <LabeledField label="（一）检查方法" type="textarea" value={insp.method}
        onChange={v => updateReport('inspection.method', v)} />

      <div style={sectionLabel}>（二）检查设备</div>
      <div style={sectionPad}>
        <Text strong style={{ display: 'block', marginBottom: 4 }}>1、硬件设备</Text>
        <EditableField type="select" value={insp.hardware_device}
          onChange={v => updateReport('inspection.hardware_device', v)} options={deviceOptions} />
        <Text strong style={{ display: 'block', marginBottom: 4, marginTop: 12 }}>
          {insp.software_tools?.length ? `2～${insp.software_tools.length + 1}、软件工具` : '2、软件工具'}
        </Text>
        <SoftwareToolsList tools={insp.software_tools || []}
          onChange={v => updateReport('inspection.software_tools', v)} />
      </div>

      <div style={sectionLabel}>（三）检查过程</div>
      <div style={sectionPad}><ProcessStepsEditor steps={insp.process_steps || []}
        onChange={v => updateReport('inspection.process_steps', v)} /></div>

      <div style={sectionLabel}>（四）检查结果</div>
      <div style={{ padding: '8px 16px', background: '#fafafa', borderRadius: 6 }}>
        <Space direction="vertical" style={{ width: '100%' }} size={8}>
          {resultFields.map(([label, key]) => (
            <div key={key}>
              <Text type="secondary">{label}：</Text>
              <EditableField type="text"
                value={key === 'data_summary'
                  ? normalizeDataSummary((insp.result as any)?.[key])
                  : (insp.result as any)?.[key] || ''}
                onChange={v => updateReport(`inspection.result.${key}`,
                  key === 'data_summary' ? normalizeDataSummary(v) : v)} />
            </div>
          ))}
        </Space>
      </div>

      <Divider>附件</Divider>
      <div style={sectionLabel}>附件1：电子数据提取固定清单</div>
      <div style={sectionPad}><ExtractListEditor
        tableData={attach.extract_list || { columns: [], rows: [] }}
        onChange={v => updateReport('attachments.extract_list', v)} /></div>

      <div style={sectionLabel}>附件2：检材照片</div>
      <div style={sectionPad}><ImageUploader photos={photoFiles} onChange={onPhotoFilesChange} /></div>

      <LabeledField label="附件3：光盘编号" type="text" value={attach.disc_number}
        onChange={v => updateReport('attachments.disc_number', v)} />
      <DateTimeField label="附件3：刻录时间" precision="date" value={attach.burning_date || ''}
        onChange={v => updateReport('attachments.burning_date', v)} />

      <Divider />
      <Space>
        <Button type="primary" size="large" icon={<DownloadOutlined />}
          onClick={onExport} loading={exporting}>导出 Word (.docx)</Button>
        <Button size="large" onClick={onBackToUpload}>返回重新上传</Button>
      </Space>
    </div>
  )
}

/** 局部辅助：标签 + EditableField 组合 */
function LabeledField({ label, type, value, onChange, placeholder }: {
  label: string; type: 'text' | 'textarea'; value: string;
  onChange: (v: string) => void; placeholder?: string;
}) {
  return <>
    <div style={{ fontWeight: 600, marginBottom: 4, marginTop: 12 }}>{label}</div>
    <EditableField type={type} value={value} onChange={onChange} placeholder={placeholder} />
  </>
}
