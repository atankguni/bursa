import { useQuery } from '@tanstack/react-query'
import { fetchStocks } from '../api'
import { useSettings } from '../lib/settings'
import { queryKeys } from './keys'

/** Stocks for the selected indices, polled per the auto-refresh setting. */
export function useStocks(indexes: string[]) {
  const { settings } = useSettings()
  return useQuery({
    queryKey: queryKeys.stocks(indexes),
    queryFn: () => fetchStocks(indexes),
    refetchInterval: settings.autoRefresh ? settings.refreshSeconds * 1000 : false,
  })
}
