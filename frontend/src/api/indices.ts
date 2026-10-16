import { api } from './client'
import type { ChartSpan, IndexHistory, MarketIndex } from './types'

export async function fetchIndices(): Promise<MarketIndex[]> {
  const { data } = await api.get<MarketIndex[]>('/api/indices')
  return data
}

export async function fetchIndexHistory(
  code: string,
  range: ChartSpan,
): Promise<IndexHistory> {
  // The first request for IHSG/LQ45/JII fetches decades of history from the provider.
  const { data } = await api.get<IndexHistory>(`/api/indices/${code}/history`, {
    params: { range },
    timeout: 60_000,
  })
  return data
}
