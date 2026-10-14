import { useQuery } from '@tanstack/react-query'
import { fetchWatchlist } from '../api'
import { useSettings } from '../lib/settings'
import { queryKeys } from './keys'

/** The saved watchlist. Poll only where prices are shown, and only if enabled. */
export function useWatchlist(options?: { poll?: boolean }) {
  const { settings } = useSettings()
  const interval =
    options?.poll && settings.autoRefresh ? settings.refreshSeconds * 1000 : false
  return useQuery({
    queryKey: queryKeys.watchlist,
    queryFn: fetchWatchlist,
    refetchInterval: interval,
  })
}
