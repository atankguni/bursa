// Shared number/date formatting helpers (standard English, IDR amounts).

const nf = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 })

// Global display mode, kept in sync with the settings store (see SettingsPanel).
// "compact" abbreviates large magnitudes (1.23T); "full" prints separators.
let compactNumbers = true
export function setCompactNumbers(on: boolean) {
  compactNumbers = on
}

/** Plain price/number with thousands separators. */
export const fmtPrice = (v: number | null | undefined) => (v == null ? '—' : nf.format(v))

/** Large magnitudes: compact (T/B/M/K) or full separators per the display mode. */
export const fmtCompact = (v: number | null | undefined) => {
  if (v == null) return '—'
  if (!compactNumbers) return nf.format(v)
  const abs = Math.abs(v)
  if (abs >= 1_000_000_000_000) return `${(v / 1_000_000_000_000).toFixed(2)}T`
  if (abs >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(2)}B`
  if (abs >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}M`
  if (abs >= 1_000) return `${(v / 1_000).toFixed(1)}K`
  return String(v)
}

/** Alias used by the price table's volume column. */
export const fmtVolume = fmtCompact

/** Signed absolute change. */
export const fmtChange = (v: number | null | undefined) =>
  v == null ? '' : `${v > 0 ? '+' : ''}${v.toFixed(2)}`

/** Signed percentage change (v is already a percent, e.g. 1.23 -> +1.23%). */
export const fmtPct = (v: number | null | undefined) =>
  v == null ? '' : `${v > 0 ? '+' : ''}${v.toFixed(2)}%`

/** Fixed-decimal ratio (PBV, etc.). */
export const fmtRatio = (v: number | null | undefined, digits = 2) =>
  v == null ? '—' : v.toFixed(digits)

/** Fraction -> percent (RoE, e.g. 0.21 -> 21.00%). */
export const fmtPercent = (v: number | null | undefined, digits = 2) =>
  v == null ? '—' : `${(v * 100).toFixed(digits)}%`

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

export const fmtDateTime = (iso: string | null | undefined) =>
  parseServerTime(iso)?.toLocaleString('en-US') ?? '—'

/** Short day + time for event lists, e.g. "16 Oct, 10:28". */
export const fmtShortDateTime = (iso: string | null | undefined) =>
  parseServerTime(iso)?.toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }) ?? '—'

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
