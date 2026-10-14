// Shared number/date formatting helpers (standard English, IDR amounts).

const nf = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 })

/** Plain price/number with thousands separators. */
export const fmtPrice = (v: number | null | undefined) => (v == null ? '—' : nf.format(v))

/** Compact large magnitudes: T / B / M / K. */
export const fmtCompact = (v: number | null | undefined) => {
  if (v == null) return '—'
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

export const fmtDateTime = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString('en-US') : '—'
