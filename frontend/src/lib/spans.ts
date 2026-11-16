import type { ChartSpan } from '../api'

/** Chart time spans shared by the stock and index charts. */
export const SPANS: { value: ChartSpan; label: string; days: number | null }[] = [
  { value: '1m', label: '1M', days: 31 },
  { value: '3m', label: '3M', days: 92 },
  { value: '6m', label: '6M', days: 183 },
  { value: '1y', label: '1Y', days: 366 },
  { value: '5y', label: '5Y', days: 5 * 366 },
  { value: 'max', label: 'Max', days: null },
]

/**
 * ISO start of a span, or undefined for Max (fit everything). Whole days, so it
 * stays the same across re-renders (a new value would re-apply the span and undo
 * the user's zoom).
 */
export const spanStart = (span: ChartSpan) => {
  const days = SPANS.find((s) => s.value === span)?.days
  if (days == null) return undefined
  const day = new Date(Date.now() - days * 86_400_000).toISOString().slice(0, 10)
  return `${day}T00:00:00Z`
}
