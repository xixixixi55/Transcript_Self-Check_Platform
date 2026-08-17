import { describe, expect, it } from 'vitest'
import type { InspectionReport } from '@biji/shared/types'
import { applyPrimarySoftwareEdit, applyReportEdit } from '@biji/shared/utils'

const report: InspectionReport = {
  title: '合成笔录', document_number: 'DOC-001',
  introduction: {
    entrust_unit: '', entrust_persons: [], entrust_time: '', case_summary: '', evidence_list: [],
    inspection_requirement: '', inspection_time_range: '', inspectors: [], inspection_place: '',
  },
  inspection: {
    method: '', hardware_device: '', software_tools: [
      { name: 'WinRAR压缩管理软件', version: '6.24' },
      { name: 'Python hashlib', version: '3.11.0' },
    ], process_steps: [],
    result: { evidence_number: '', software_name: '', software_version: '', data_summary: '', rar_filename: '', md5_hash: '', file_size: '' },
  },
  attachments: { extract_list: { columns: [], rows: [] }, photo_ids: [], disc_number: '' },
}

describe('primary software projection', () => {
  it('marks a complete user edit and derives legacy fields/tools', () => {
    const next = applyPrimarySoftwareEdit(report, 'name', '人工工具')
    const updated = applyPrimarySoftwareEdit(next, 'version', 'V2.0.0')
    expect(updated.inspection.primary_software?.confirmation_status).toBe('confirmed_by_user')
    expect(updated.inspection.result.software_name).toBe('人工工具')
    expect(updated.inspection.result.software_version).toBe('V2.0.0')
    expect(updated.inspection.software_tools[0]).toEqual({ name: '人工工具', version: 'V2.0.0' })
  })

  it('returns to unconfirmed when either required field is cleared', () => {
    const next = applyPrimarySoftwareEdit(report, 'version', '')
    expect(next.inspection.primary_software?.confirmation_status).toBe('unconfirmed')
    expect(next.inspection.result.software_version).toBe('')
    expect(next.inspection.software_tools).toHaveLength(2)
  })

  it('keeps HashMyFiles as a runtime tool alongside legacy Python hashlib', () => {
    const hashReport: InspectionReport = {
      ...report,
      inspection: {
        ...report.inspection,
        software_tools: [
          { name: 'WinRAR压缩管理软件', version: '6.24' },
          { name: 'Python hashlib', version: '3.11.0' },
          { name: 'HashMyFiles', version: '2.51' },
        ],
      },
    }
    const next = applyPrimarySoftwareEdit(hashReport, 'version', '')
    const runtimeNames = next.inspection.software_tools.map(tool => tool.name)
    expect(runtimeNames).toContain('HashMyFiles')
    expect(runtimeNames).toContain('Python hashlib')
    expect(runtimeNames).toContain('WinRAR压缩管理软件')
  })
})

const firstMaterial = {
  id: 'SYNTHETIC-MATERIAL-1', device_type: 'phone', device_name: 'SYNTHETIC PHONE 1',
  imei1: 'SYNTHETIC-IMEI-1', evidence_number: 'SYNTHETIC-1', material_type: 'phone' as const,
}
const secondMaterial = {
  id: 'SYNTHETIC-MATERIAL-2', device_type: 'tablet', device_name: 'SYNTHETIC TABLET 2',
  serial_number: 'SYNTHETIC-SERIAL-2', evidence_number: 'SYNTHETIC-2', material_type: 'tablet' as const,
}
const photoIds = [
  'asset-synthetic-1-front', 'asset-synthetic-1-back',
  'asset-synthetic-2-front', 'asset-synthetic-2-back',
]

function evidenceReport(): InspectionReport {
  return {
    ...report,
    introduction: { ...report.introduction, evidence_list: [firstMaterial] },
    inspection: {
      ...report.inspection,
      primary_software: {
        name: 'SYNTHETIC TOOL', version: '1.0', display_name: 'SYNTHETIC TOOL 1.0',
        confirmation_status: 'confirmed_by_report', provenance: [], candidates: [],
      },
      process_steps: [
        { step_number: 1, content: 'old material description' },
        { step_number: 2, content: 'old photo description' },
        { step_number: 3, content: 'SYNTHETIC unchanged environment step' },
        { step_number: 4, content: 'old inspection description' },
      ],
      result: { ...report.inspection.result, evidence_number: 'SYNTHETIC-1' },
    },
    attachments: {
      ...report.attachments,
      photo_ids: photoIds,
      photo_groups: [{
        material_id: firstMaterial.id, material_number: firstMaterial.evidence_number,
        display_text: '检材SYNTHETIC-1照片',
        ordered_image_ids: [photoIds[0], photoIds[1]], source_order: 1,
      }],
    },
  }
}

describe('evidence list projection', () => {
  it('marks an identifier-free material as unable to extract in process step 1', () => {
    const unavailable = {
      ...firstMaterial, imei1: '', extractable: false, device_name: 'SYNTHETIC PHONE OFF',
    }
    const updated = applyReportEdit(
      evidenceReport(), 'introduction.evidence_list', [unavailable],
    )
    expect(updated.inspection.process_steps.find(step => step.step_number === 1)?.content)
      .toContain('将SYNTHETIC PHONE OFF（无法提取）编号为SYNTHETIC-1。')
  })

  it('updates process/result fields and rebuilds existing photo groups after adding a material', () => {
    const initial = evidenceReport()

    const updated = applyReportEdit(
      initial, 'introduction.evidence_list', [firstMaterial, secondMaterial],
    )

    expect(updated.inspection.result.evidence_number).toBe('SYNTHETIC-1、SYNTHETIC-2')
    expect(updated.inspection.process_steps.find(step => step.step_number === 1)?.content)
      .toContain('SYNTHETIC TABLET 2（序列号：SYNTHETIC-SERIAL-2）编号为SYNTHETIC-2')
    expect(updated.inspection.process_steps.find(step => step.step_number === 2)?.content)
      .toBe('对检材SYNTHETIC-1、SYNTHETIC-2进行拍照。')
    expect(updated.inspection.process_steps.find(step => step.step_number === 3)?.content)
      .toBe('SYNTHETIC unchanged environment step')
    expect(updated.inspection.process_steps.find(step => step.step_number === 4)?.content)
      .toBe('启动SYNTHETIC TOOL（版本号为1.0）对检材SYNTHETIC-1、SYNTHETIC-2进行检查。')
    expect(updated.attachments.photo_groups).toEqual([
      {
        material_id: 'SYNTHETIC-MATERIAL-1', material_number: 'SYNTHETIC-1',
        display_text: '检材SYNTHETIC-1照片',
        ordered_image_ids: photoIds.slice(0, 2), source_order: 1,
      },
      {
        material_id: 'SYNTHETIC-MATERIAL-2', material_number: 'SYNTHETIC-2',
        display_text: '检材SYNTHETIC-2照片',
        ordered_image_ids: photoIds.slice(2, 4), source_order: 2,
      },
    ])
  })

  it('keeps renumber, reorder, removal and mismatched photo state deterministic', () => {
    const added = applyReportEdit(
      evidenceReport(), 'introduction.evidence_list', [firstMaterial, secondMaterial],
    )
    const renumberedSecond = { ...secondMaterial, evidence_number: 'SYNTHETIC-2-UPDATED' }
    const renumbered = applyReportEdit(
      added, 'introduction.evidence_list', [firstMaterial, renumberedSecond],
    )

    expect(renumbered.inspection.result.evidence_number).toBe('SYNTHETIC-1、SYNTHETIC-2-UPDATED')
    expect(renumbered.inspection.process_steps.find(step => step.step_number === 2)?.content)
      .toContain('SYNTHETIC-1、SYNTHETIC-2-UPDATED')
    expect(renumbered.attachments.photo_groups?.[1]).toEqual(expect.objectContaining({
      material_number: 'SYNTHETIC-2-UPDATED', display_text: '检材SYNTHETIC-2-UPDATED照片',
    }))

    const reordered = applyReportEdit(
      renumbered, 'introduction.evidence_list', [renumberedSecond, firstMaterial],
    )
    expect(reordered.inspection.result.evidence_number).toBe('SYNTHETIC-2-UPDATED、SYNTHETIC-1')
    expect(reordered.attachments.photo_groups?.map(group => ({
      material: group.material_id, images: group.ordered_image_ids,
    }))).toEqual([
      { material: 'SYNTHETIC-MATERIAL-2', images: photoIds.slice(0, 2) },
      { material: 'SYNTHETIC-MATERIAL-1', images: photoIds.slice(2, 4) },
    ])
    expect(reordered.inspection.process_steps.find(step => step.step_number === 3)?.content)
      .toBe('SYNTHETIC unchanged environment step')

    const removed = applyReportEdit(
      reordered, 'introduction.evidence_list', [renumberedSecond],
    )
    expect(removed.inspection.result.evidence_number).toBe('SYNTHETIC-2-UPDATED')
    expect(removed.inspection.process_steps.map(step => step.content).join(' ')).not.toContain('SYNTHETIC-1')
    expect(removed.attachments.photo_ids).toEqual(photoIds)
    expect(removed.attachments.photo_groups).toHaveLength(1)
    expect(removed.attachments.photo_groups?.flatMap(group => group.ordered_image_ids))
      .toEqual(photoIds.slice(0, 2))
    expect(removed.attachments.photo_groups?.length).not.toBe(removed.attachments.photo_ids.length / 2)
  })
})

describe('inspection environment projection', () => {
  const environmentReport = (): InspectionReport => ({
    ...evidenceReport(),
    inspection: {
      ...evidenceReport().inspection,
      hardware_device: 'SYNTHETIC DEVICE A',
      environment_snapshot: {
        operating_system: { display_name: 'Windows 11 TEST专业版 64位', status: 'detected' },
        security_software: { name: '火绒安全软件', version: 'TEST-6.0.7.0', status: 'detected' },
      },
    },
  })

  it('reprojects only step 3 from the saved snapshot when hardware changes', () => {
    const initial = environmentReport()
    const updated = applyReportEdit(initial, 'inspection.hardware_device', 'SYNTHETIC DEVICE B')
    const steps = updated.inspection.process_steps

    expect(steps.find(step => step.step_number === 3)?.content)
      .toBe('启动SYNTHETIC DEVICE B，Windows 11 TEST专业版 64位启动正常，使用火绒安全软件（版本号为TEST-6.0.7.0）对SYNTHETIC DEVICE B进行杀毒，未发现病毒，完毕后退出火绒安全软件。')
    expect(steps.filter(step => step.step_number !== 3))
      .toEqual(initial.inspection.process_steps.filter(step => step.step_number !== 3))
  })

  it('uses pending language without a false clean result when Huorong is not found', () => {
    const initial = environmentReport()
    initial.inspection.environment_snapshot = {
      operating_system: { display_name: '', status: 'unavailable' },
      security_software: { name: '', version: '', status: 'not_found' },
    }
    const updated = applyReportEdit(initial, 'inspection.hardware_device', '')
    const content = updated.inspection.process_steps.find(step => step.step_number === 3)?.content

    expect(content).toContain('检查硬件设备待确认')
    expect(content).toContain('操作系统信息待确认')
    expect(content).toContain('安全软件待确认（版本号待确认）')
    expect(content).toContain('杀毒的结果待确认')
    expect(content).not.toContain('未发现病毒')
  })

  it('keeps a legacy step unchanged when the saved snapshot is absent', () => {
    const initial = evidenceReport()
    const updated = applyReportEdit(initial, 'inspection.hardware_device', 'SYNTHETIC DEVICE B')
    expect(updated.inspection.process_steps.find(step => step.step_number === 3)?.content)
      .toBe('SYNTHETIC unchanged environment step')
  })
})
