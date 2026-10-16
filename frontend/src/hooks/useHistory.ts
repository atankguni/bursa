import { useQuery } from '@tanstack/react-query'
import { fetchHistory, type ChartSpan } from '../api'
import { queryKeys } from './keys'

/** Spans served from the regular ~1y of stored bars (the chart zooms within them). */
const STORED: ChartSpan[] = ['1m', '3m', '6m', '1y']

/**
 * OHLCV bars for a ticker/interval. For daily bars, short spans share one 1y
 * request; 5Y/Max request their own range. Idle until `enabled`.
 */
export function useHistory(
  ticker: string,
  interval: '1d' | '1m',
  span: ChartSpan = '1y',
  enabled = true,
) {
  const range = interval === '1d' ? (STORED.includes(span) ? '1y' : span) : undefined
  return useQuery({
    queryKey: queryKeys.history(ticker, interval, range),
    queryFn: () => fetchHistory(ticker, interval, range),
    enabled,
    placeholderData: (prev) => prev, // keep the current chart while a longer span loads
  })
}
