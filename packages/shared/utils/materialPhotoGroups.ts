// Layer 2: SharedUtils — deterministic material/photo pairing for Attachment 2.
import type { InspectionReport, MaterialPhotoGroup } from '../types'

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
