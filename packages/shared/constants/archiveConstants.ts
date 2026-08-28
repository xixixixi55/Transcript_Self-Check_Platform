/** 固定的生产归档策略。1 GB 按 1024^3 字节解释。 */
export const ARCHIVE_GB_BYTES = 1024 ** 3

export const ARCHIVE_VOLUME_TIERS = [
  { gb: 4, volume_size_bytes: 4 * ARCHIVE_GB_BYTES, max_part_count: 2 },
  { gb: 22, volume_size_bytes: 22 * ARCHIVE_GB_BYTES, max_part_count: 2 },
  { gb: 45, volume_size_bytes: 45 * ARCHIVE_GB_BYTES, max_part_count: 5 },
] as const

/** 标准分卷模式阈值；更大的输入使用单个不分卷 RAR。 */
export const ARCHIVE_STANDARD_SPLIT_MAX_INPUT_BYTES = 225 * ARCHIVE_GB_BYTES
export const ARCHIVE_MAX_REPLAN_ATTEMPTS = 2

/** 按升序排列的光盘容量档位；用于选择可容纳分卷实际
 *  `size_bytes` 的最小容量。 */
export const DISC_CAPACITY_BYTES = [
  4 * ARCHIVE_GB_BYTES,
  22 * ARCHIVE_GB_BYTES,
  45 * ARCHIVE_GB_BYTES,
] as const

/** 最大光盘容量；超过此大小的分卷无效。 */
export const DISC_MAX_CAPACITY_BYTES = 45 * ARCHIVE_GB_BYTES
