/** Parse ISO strings, Date, or epoch ms into a Date (local timezone). */
function parseDate(input: string | Date | number): Date | null {
  if (input instanceof Date) return Number.isNaN(input.getTime()) ? null : input
  const d = new Date(input)
  return Number.isNaN(d.getTime()) ? null : d
}

/** HH:MM:SS (24-hour, zero-padded). */
export function formatTimeHms(input: string | Date | number): string {
  const raw = String(input).trim()
  const clockOnly = /^(\d{1,2}):(\d{2}):(\d{2})$/.exec(raw)
  if (clockOnly) {
    const [, h, m, s] = clockOnly
    return `${h.padStart(2, '0')}:${m}:${s}`
  }
  const d = parseDate(input)
  if (!d) return raw
  const h = String(d.getHours()).padStart(2, '0')
  const m = String(d.getMinutes()).padStart(2, '0')
  const s = String(d.getSeconds()).padStart(2, '0')
  return `${h}:${m}:${s}`
}

/** e.g. 2 Jun 2025, 14:30:05 */
export function formatDateTime(input: string | Date | number): string {
  const raw = String(input).trim()
  const d = parseDate(input)
  if (!d) return raw
  const datePart = d.toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
  return `${datePart}, ${formatTimeHms(d)}`
}

/** Time-only for status lines; date+time when value looks like a full timestamp. */
export function formatDisplayTimestamp(input: string | Date | number | null | undefined): string {
  if (input == null || input === '') return ''
  const raw = String(input).trim()
  if (/^\d{1,2}:\d{2}:\d{2}$/.test(raw)) return formatTimeHms(raw)
  if (raw.includes('T') || raw.includes('-')) return formatDateTime(raw)
  return formatTimeHms(raw)
}
