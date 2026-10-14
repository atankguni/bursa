import { useQuery } from '@tanstack/react-query'
import { fetchMarketStatus } from '../api'
import { queryKeys } from './keys'

/** IDX trading status (open / break / closed), refreshed every 30s. */
export function useMarketStatus() {
  return useQuery({
    queryKey: queryKeys.marketStatus,
    queryFn: fetchMarketStatus,
    refetchInterval: 30_000,
  })
}
