import { useQuery } from '@tanstack/react-query'
import { fetchStatus } from '../api'
import { useSettings } from '../lib/settings'
import { queryKeys } from './keys'

/** Global app status (footer): last sync, provider, session, counts. */
export function useStatus() {
  const { settings } = useSettings()
  return useQuery({
    queryKey: queryKeys.status,
    queryFn: fetchStatus,
    refetchInterval: settings.autoRefresh ? 60_000 : false,
  })
}
