// Shared number/date formatting helpers (IDR amounts). The number style (1,234.50
// or the Indonesian 1.234,50) and date style (16 Nov 2026 or 16/11/2026) follow
// Settings → Display; the settings store keeps the flags below in sync.

export type NumberLocale = 'en' | 'id'
export type DateStyle = 'text' | 'numeric'

// Global display modes, kept in sync with the settings store (lib/settings).
// "compact" abbreviates large magnitudes (1.23T); "full" prints separators.
let compactNumbers = true
let numberLocale: NumberLocale = 'en'
let dateStyle: DateStyle = 'text'
export function setCompactNumbers(on: boolean) {
  compactNumbers = on
}
export function setNumberLocale(locale: NumberLocale) {
  numberLocale = locale
}
export function setDateStyle(style: DateStyle) {
  dateStyle = style
}

const formats = new Map<string, Intl.NumberFormat>()

/**
 * A number in the chosen style, with `min`–`max` decimals: fmtNum(1234.5, 2) is
 * "1,234.50" (or "1.234,50"). Use this, not toFixed, for anything shown.
 */
export function fmtNum(v: number, min = 0, max = min): string {
  const tag = numberLocale === 'id' ? 'id-ID' : 'en-US'
  const key = `${tag}|${min}|${max}`
  let f = formats.get(key)
  if (!f) {
    f = new Intl.NumberFormat(tag, {
      minimumFractionDigits: min,
      maximumFractionDigits: max,
    })
    formats.set(key, f)
  }
  return f.format(v)
}

/** "+1.23" / "-1.23" / "0.00": a signed number with fixed decimals. */
const signed = (v: number, digits: number) => `${v > 0 ? '+' : ''}${fmtNum(v, digits)}`

/** A rupiah amount, whole rupiah (no decimals): 1,192,799. */
export const fmtMoney = (v: number | null | undefined) =>
  v == null ? '—' : fmtNum(Math.round(v) || 0) // || 0: no "-0"

/** Signed rupiah amount: +1,200 / −3,400 (true minus sign). */
export const fmtMoneySigned = (v: number | null | undefined) => {
  if (v == null) return '—'
  const r = Math.round(v)
  return `${r > 0 ? '+' : r < 0 ? '−' : ''}${fmtNum(Math.abs(r))}`
}

/** Plain price/number with thousands separators (up to 2 decimals). */
export const fmtPrice = (v: number | null | undefined) =>
  v == null ? '—' : fmtNum(v, 0, 2)

/** Large magnitudes: compact (T/B/M/K) or full separators per the display mode. */
export const fmtCompact = (v: number | null | undefined) => {
  if (v == null) return '—'
  if (!compactNumbers) return fmtNum(v, 0, 2)
  const abs = Math.abs(v)
  if (abs >= 1_000_000_000_000) return `${fmtNum(v / 1_000_000_000_000, 2)}T`
  if (abs >= 1_000_000_000) return `${fmtNum(v / 1_000_000_000, 2)}B`
  if (abs >= 1_000_000) return `${fmtNum(v / 1_000_000, 2)}M`
  if (abs >= 1_000) return `${fmtNum(v / 1_000, 1)}K`
  return fmtNum(v, 0, 2)
}

/** Alias used by the price table's volume column. */
export const fmtVolume = fmtCompact

/** Signed absolute change. */
export const fmtChange = (v: number | null | undefined) => (v == null ? '' : signed(v, 2))

/** Signed percentage change (v is already a percent, e.g. 1.23 -> +1.23%). */
export const fmtPct = (v: number | null | undefined) =>
  v == null ? '' : `${signed(v, 2)}%`

/** Fixed-decimal ratio (PBV, etc.). */
export const fmtRatio = (v: number | null | undefined, digits = 2) =>
  v == null ? '—' : fmtNum(v, digits)

/** Fraction -> percent (RoE, e.g. 0.21 -> 21.00%). */
export const fmtPercent = (v: number | null | undefined, digits = 2) =>
  v == null ? '—' : `${fmtNum(v * 100, digits)}%`

/**
 * Parse a backend timestamp. Stored times (price bars, alert events) arrive as
 * UTC without an offset, e.g. "2026-10-16T03:52:00"; `new Date` would read those
 * as *local* time, so they get "Z". Values that already carry an offset
 * ("...Z", "+07:00") are used as-is. Returns null when unparseable.
 */
export function parseServerTime(iso: string | null | undefined): Date | null {
  if (!iso) return null
  // Only full timestamps get "Z"; a bare date ("2026-10-16") is already UTC.
  const naive = iso.includes('T') && !/(Z|[+-]\d{2}:?\d{2})$/i.test(iso)
  const d = new Date(naive ? `${iso}Z` : iso)
  return Number.isNaN(d.getTime()) ? null : d
}

/**
 * A day in the chosen style: "16 Nov 2026" or "16/11/2026". A bare date
 * ("2026-11-16") is shown as that date wherever the browser is; a timestamp in
 * the browser's time zone unless `timeZone` is given.
 */
export function fmtDay(
  value: string | Date | null | undefined,
  o: { year?: boolean; weekday?: boolean; long?: boolean; timeZone?: string } = {},
): string {
  const bare = typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)
  const d =
    value instanceof Date
      ? value
      : bare
        ? new Date(`${value}T00:00:00Z`)
        : parseServerTime(value)
  if (!d || Number.isNaN(d.getTime())) return '—'
  const opts: Intl.DateTimeFormatOptions =
    dateStyle === 'numeric'
      ? { day: '2-digit', month: '2-digit' }
      : { day: 'numeric', month: o.long ? 'long' : 'short' }
  if (o.year ?? true) opts.year = 'numeric'
  if (o.weekday) opts.weekday = 'short'
  const tz = o.timeZone ?? (bare ? 'UTC' : undefined)
  if (tz) opts.timeZone = tz
  return new Intl.DateTimeFormat('en-GB', opts).format(d)
}

const clock = (d: Date) =>
  new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit' }).format(d)

/** Day and time, e.g. "16 Nov 2026, 10:28". */
export const fmtDateTime = (iso: string | null | undefined) => {
  const d = parseServerTime(iso)
  return d ? `${fmtDay(d)}, ${clock(d)}` : '—'
}

/** Short day + time for event lists, e.g. "16 Nov, 10:28" (or "16/11, 10:28"). */
export const fmtShortDateTime = (iso: string | null | undefined) => {
  const d = parseServerTime(iso)
  return d ? `${fmtDay(d, { year: false })}, ${clock(d)}` : '—'
}

/** Relative age, e.g. "just now", "5m ago", "3h ago", "2d ago". */
export function fmtTimeAgo(iso: string | null | undefined, now = Date.now()): string {
  const then = parseServerTime(iso)
  if (!then) return '—'
  const mins = Math.max(0, Math.round((now - then.getTime()) / 60000))
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.round(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.round(hours / 24)}d ago`
}
