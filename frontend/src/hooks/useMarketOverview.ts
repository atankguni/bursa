import { useQuery } from '@tanstack/react-query'
import { fetchMarketOverview } from '../api'
import { queryKeys } from './keys'

/** Breadth, top movers, and sector performance. */
export function useMarketOverview() {
  return useQuery({
    queryKey: queryKeys.marketOverview,
    queryFn: fetchMarketOverview,
  })
}
