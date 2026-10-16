import { useQuery } from '@tanstack/react-query'
import { fetchScreener, fetchSyncStatus, type ScreenerFilters } from '../api'
import { queryKeys } from './keys'

/** One page of the ranked/filtered universe. `page` is 0-based. */
export function useScreener(filters: ScreenerFilters, page: number, pageSize: number) {
  return useQuery({
    queryKey: queryKeys.screener({ ...filters, page, pageSize }),
    queryFn: () => fetchScreener(filters, pageSize, page * pageSize),
    placeholderData: (prev) => prev, // keep the current page visible while the next loads
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
