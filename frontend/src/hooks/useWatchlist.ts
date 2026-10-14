import { useQuery } from '@tanstack/react-query'
import { fetchWatchlist } from '../api'
import { queryKeys } from './keys'

/** The saved watchlist. Poll only where prices are actually shown. */
export function useWatchlist(options?: { poll?: boolean }) {
  return useQuery({
    queryKey: queryKeys.watchlist,
    queryFn: fetchWatchlist,
    refetchInterval: options?.poll ? 60_000 : false,
  })
}
