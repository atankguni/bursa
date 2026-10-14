import { useQuery } from '@tanstack/react-query'
import { fetchScreener, fetchSyncStatus, type ScreenerFilters } from '../api'
import { queryKeys } from './keys'

/** Ranked/filtered universe (recommendation score + fundamentals). */
export function useScreener(filters: ScreenerFilters) {
  return useQuery({
    queryKey: queryKeys.screener(filters),
    queryFn: () => fetchScreener(filters),
  })
}

/** Progress of the background "sync missing data" job (polls while running). */
export function useSyncStatus() {
  return useQuery({
    queryKey: queryKeys.syncStatus,
    queryFn: fetchSyncStatus,
    refetchInterval: (query) => (query.state.data?.running ? 1500 : false),
  })
}
