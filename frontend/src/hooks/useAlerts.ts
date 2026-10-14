import { useQuery } from '@tanstack/react-query'
import { fetchAlertEvents, fetchAlerts } from '../api'
import { useSettings } from '../lib/settings'
import { queryKeys } from './keys'

/** Alert rules. */
export function useAlerts() {
  return useQuery({ queryKey: queryKeys.alerts, queryFn: fetchAlerts })
}

/** Recent triggered events (drives the navbar bell). */
export function useAlertEvents() {
  const { settings } = useSettings()
  return useQuery({
    queryKey: queryKeys.alertEvents,
    queryFn: () => fetchAlertEvents(30),
    refetchInterval: settings.autoRefresh
      ? Math.max(settings.refreshSeconds * 1000, 60_000)
      : false,
  })
}
