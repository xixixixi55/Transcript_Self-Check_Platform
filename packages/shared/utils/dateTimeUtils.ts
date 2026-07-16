type DateParts = { year: number; month: number; day: number }

export interface DateTimeRangeInputValues {
  start: string
  end: string
}

function toDateParts(year: number, month: number, day: number): DateParts | null {
  const date = new Date(Date.UTC(year, month - 1, day))
  if (date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) {
    return null
  }
  return { year, month, day }
}

function parseDateParts(value: string): DateParts | null {
  const trimmed = value.trim()
  const chinese = /^(\d{4})年(\d{1,2})月(\d{1,2})日$/.exec(trimmed)
  const iso = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(trimmed)
  const match = chinese || iso
  return match ? toDateParts(Number(match[1]), Number(match[2]), Number(match[3])) : null
}

function parseDateTime(value: string): { date: DateParts; hour: number; minute: number } | null {
  const chinese = /^(\d{4})年(\d{1,2})月(\d{1,2})日(\d{1,2})点(\d{1,2})分$/.exec(value.trim())
  const iso = /^(\d{4})-(\d{1,2})-(\d{1,2})[ T](\d{1,2}):(\d{2})(?::\d{2})?$/.exec(value.trim())
  const match = chinese || iso
  if (!match) return null
  const date = toDateParts(Number(match[1]), Number(match[2]), Number(match[3]))
  const hour = Number(match[4])
  const minute = Number(match[5])
  if (!date || hour < 0 || hour > 23 || minute < 0 || minute > 59) return null
  return { date, hour, minute }
}

function formatInputDate(date: DateParts): string {
  return `${date.year.toString().padStart(4, '0')}-${date.month.toString().padStart(2, '0')}-${date.day.toString().padStart(2, '0')}`
}

function formatInputDateTime(value: { date: DateParts; hour: number; minute: number }): string {
  return `${formatInputDate(value.date)}T${value.hour.toString().padStart(2, '0')}:${value.minute.toString().padStart(2, '0')}`
}

function formatChineseDate(date: DateParts): string {
  return `${date.year}年${date.month}月${date.day}日`
}

function parseRangeParts(value: string): { start: ReturnType<typeof parseDateTime>; end: ReturnType<typeof parseDateTime> } | null {
  const separator = value.includes('至') ? '至' : ' ~ '
  const parts = value.split(separator)
  if (parts.length !== 2) return null
  const start = parseDateTime(parts[0])
  const end = parseDateTime(parts[1])
  return start && end ? { start, end } : null
}

/** 将业务层的纯日期转换为 HTML 日期控件值。 */
export function toDateInputValue(value: string): string {
  const date = parseDateParts(value)
  return date ? formatInputDate(date) : ''
}

/** 将 HTML 日期控件值转换回当前业务使用的中文日期格式。 */
export function fromDateInputValue(value: string): string {
  const date = parseDateParts(value)
  return date ? formatChineseDate(date) : ''
}

export function isValidDateFieldValue(value: string): boolean {
  return !value.trim() || parseDateParts(value) !== null
}

/** 将当前分钟精度的检查时间范围转换为两个 HTML 日期时间控件值。 */
export function toDateTimeRangeInputValues(value: string): DateTimeRangeInputValues {
  const range = parseRangeParts(value)
  return range
    ? { start: formatInputDateTime(range.start!), end: formatInputDateTime(range.end!) }
    : { start: '', end: '' }
}

/** 将两个 HTML 日期时间控件值转换回现有的分钟精度中文范围格式。 */
export function fromDateTimeRangeInputValues(startValue: string, endValue: string): string {
  const start = parseDateTime(startValue.replace('T', ' '))
  const end = parseDateTime(endValue.replace('T', ' '))
  if (!start || !end) return ''
  return `${formatChineseDate(start.date)}${start.hour}点${start.minute.toString().padStart(2, '0')}分至${formatChineseDate(end.date)}${end.hour}点${end.minute.toString().padStart(2, '0')}分`
}

export function isValidMinuteTimeRangeValue(value: string): boolean {
  if (!value.trim()) return true
  const range = parseRangeParts(value)
  if (!range || !range.start || !range.end) return false
  const start = new Date(Date.UTC(range.start.date.year, range.start.date.month - 1, range.start.date.day, range.start.hour, range.start.minute))
  const end = new Date(Date.UTC(range.end.date.year, range.end.date.month - 1, range.end.date.day, range.end.hour, range.end.minute))
  return start.getTime() <= end.getTime()
}

export function isCompleteDateTimeRange(startValue: string, endValue: string): boolean {
  return Boolean(parseDateTime(startValue.replace('T', ' ')) && parseDateTime(endValue.replace('T', ' ')))
}
