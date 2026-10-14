import { useQuery } from '@tanstack/react-query'
import { fetchStocks } from '../api'
import { queryKeys } from './keys'

/** Stocks for the selected indices, polled to mirror the backend sync cadence. */
export function useStocks(indexes: string[]) {
  return useQuery({
    queryKey: queryKeys.stocks(indexes),
    queryFn: () => fetchStocks(indexes),
    refetchInterval: 60_000,
  })
}
