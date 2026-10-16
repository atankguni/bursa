import { useQuery } from '@tanstack/react-query'
import { fetchIndexHistory, fetchIndices, type ChartSpan } from '../api'
import { useSettings } from '../lib/settings'
import { queryKeys } from './keys'

/** Latest value of every IDX index (refreshed server-side every 15 min while trading). */
export function useIndices() {
  const { settings } = useSettings()
  return useQuery({
    queryKey: queryKeys.indices,
    queryFn: fetchIndices,
    refetchInterval: settings.autoRefresh ? settings.refreshSeconds * 1000 : false,
  })
}

/** Daily bars for one index. Short spans share the 1Y request (the chart zooms). */
export function useIndexHistory(code: string, span: ChartSpan, enabled = true) {
  const range: ChartSpan = ['1m', '3m', '6m'].includes(span) ? '1y' : span
  return useQuery({
    queryKey: queryKeys.indexHistory(code, range),
    queryFn: () => fetchIndexHistory(code, range),
    enabled,
    placeholderData: (prev) => prev,
  })
}
