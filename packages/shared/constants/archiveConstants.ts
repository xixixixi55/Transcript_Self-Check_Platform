/** Fixed production archive policy. One named GB is 1024³ bytes. */
export const ARCHIVE_GB_BYTES = 1024 ** 3

export const ARCHIVE_VOLUME_TIERS = [
  { gb: 4, volume_size_bytes: 4 * ARCHIVE_GB_BYTES, max_part_count: 2 },
  { gb: 22, volume_size_bytes: 22 * ARCHIVE_GB_BYTES, max_part_count: 2 },
  { gb: 45, volume_size_bytes: 45 * ARCHIVE_GB_BYTES, max_part_count: 5 },
] as const

/** Upper boundary of standard multi-volume mode, not a total archive limit. */
export const ARCHIVE_STANDARD_VOLUME_MAX_INPUT_BYTES = 225 * ARCHIVE_GB_BYTES
export const ARCHIVE_MAX_REPLAN_ATTEMPTS = 2

/** Disc capacity tiers in ascending order; used to select the smallest
 *  capacity that can hold a part's actual `size_bytes`. */
export const DISC_CAPACITY_BYTES = [
  4 * ARCHIVE_GB_BYTES,
  22 * ARCHIVE_GB_BYTES,
  45 * ARCHIVE_GB_BYTES,
] as const

/** Maximum disc capacity; a part exceeding this size is invalid. */
export const DISC_MAX_CAPACITY_BYTES = 45 * ARCHIVE_GB_BYTES
