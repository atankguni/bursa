import { useQuery } from '@tanstack/react-query'
import { fetchHistory } from '../api'
import { queryKeys } from './keys'

/** OHLCV bars for a ticker/interval. Idle until `enabled`. */
export function useHistory(ticker: string, range: '1d' | '1m', enabled = true) {
  return useQuery({
    queryKey: queryKeys.history(ticker, range),
    queryFn: () => fetchHistory(ticker, range),
    enabled,
  })
}
