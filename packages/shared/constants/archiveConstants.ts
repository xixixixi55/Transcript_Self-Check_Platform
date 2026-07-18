/** Fixed production archive policy. Values are decimal bytes, never GiB. */
export const ARCHIVE_GB_BYTES = 1_000_000_000

export const ARCHIVE_VOLUME_TIERS = [
  { gb: 4, volume_size_bytes: 4 * ARCHIVE_GB_BYTES, max_part_count: 2 },
  { gb: 22, volume_size_bytes: 22 * ARCHIVE_GB_BYTES, max_part_count: 2 },
  { gb: 45, volume_size_bytes: 45 * ARCHIVE_GB_BYTES, max_part_count: 3 },
] as const

export const ARCHIVE_MAX_INPUT_BYTES = 135 * ARCHIVE_GB_BYTES
export const ARCHIVE_MAX_REPLAN_ATTEMPTS = 2
