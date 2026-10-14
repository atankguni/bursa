import { api } from './client'
import type { ScreenerRow } from './types'

export interface ScreenerFilters {
  minScore?: number
  maxPbv?: number
  minRoe?: number
  rating?: string
  sector?: string
  buyOnly?: boolean
  limit?: number
}

export async function fetchScreener(
  filters: ScreenerFilters = {},
): Promise<ScreenerRow[]> {
  const params = new URLSearchParams()
  if (filters.minScore != null) params.set('min_score', String(filters.minScore))
  if (filters.maxPbv != null) params.set('max_pbv', String(filters.maxPbv))
  if (filters.minRoe != null) params.set('min_roe', String(filters.minRoe))
  if (filters.rating) params.set('rating', filters.rating)
  if (filters.sector) params.set('sector', filters.sector)
  if (filters.buyOnly) params.set('buy_only', 'true')
  params.set('limit', String(filters.limit ?? 200))
  const { data } = await api.get<ScreenerRow[]>('/api/screener', { params })
  return data
}
