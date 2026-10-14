import { useQuery } from '@tanstack/react-query'
import { fetchScreener, type ScreenerFilters } from '../api'
import { queryKeys } from './keys'

/** Ranked/filtered universe (recommendation score + fundamentals). */
export function useScreener(filters: ScreenerFilters) {
  return useQuery({
    queryKey: queryKeys.screener(filters),
    queryFn: () => fetchScreener(filters),
  })
}
