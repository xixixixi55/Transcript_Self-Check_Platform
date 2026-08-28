// 第 2 层：SharedUtils — 附件 2 的确定性检材/照片配对。
import type { InspectionReport, MaterialPhotoGroup } from '../types'

const numericFileNameCollator = new Intl.Collator('zh-CN', {
  numeric: true,
  sensitivity: 'base',
})

export function hasNumericFileName(fileName: string): boolean {
  return /\d/u.test(fileName)
}

export function parseMaterialPhotoPosition(fileName: string): {
  materialPosition: number
  photoPosition: number
} | null {
  const stem = fileName.replace(/\.[^.]+$/u, '').trim()
  const match = /^(\d+)-(\d+)$/u.exec(stem)
  if (!match) return null
  return {
    materialPosition: Number(match[1]),
    photoPosition: Number(match[2]),
  }
}

export function sortFilesByNumericName<T extends { name: string }>(files: readonly T[]): T[] {
  return files
    .map((file, sourceIndex) => ({ file, sourceIndex }))
    .sort((left, right) => (
      numericFileNameCollator.compare(left.file.name, right.file.name)
      || left.sourceIndex - right.sourceIndex
    ))
    .map(item => item.file)
}

export function buildMaterialPhotoGroups(
  report: InspectionReport,
  orderedImageIds: string[],
): MaterialPhotoGroup[] {
  const evidenceList = report.introduction?.evidence_list || []
  const groupCount = Math.floor(orderedImageIds.length / 2)
  return evidenceList.slice(0, groupCount).map((item, index) => ({
    material_id: item.id,
    material_number: item.evidence_number,
    display_text: `检材${item.evidence_number}照片`,
    ordered_image_ids: [
      orderedImageIds[index * 2],
      orderedImageIds[index * 2 + 1],
    ],
    source_order: index + 1,
  }))
}
