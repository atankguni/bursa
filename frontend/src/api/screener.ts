import { api } from './client'
import type { ScreenerPage, SyncStatus } from './types'

export interface ScreenerFilters {
  minScore?: number
  maxPbv?: number
  minRoe?: number
  rating?: string
  sector?: string
  buyOnly?: boolean
}

export async function fetchScreener(
  filters: ScreenerFilters = {},
  limit = 100,
  offset = 0,
): Promise<ScreenerPage> {
  const params = new URLSearchParams()
  if (filters.minScore != null) params.set('min_score', String(filters.minScore))
  if (filters.maxPbv != null) params.set('max_pbv', String(filters.maxPbv))
  if (filters.minRoe != null) params.set('min_roe', String(filters.minRoe))
  if (filters.rating) params.set('rating', filters.rating)
  if (filters.sector) params.set('sector', filters.sector)
  if (filters.buyOnly) params.set('buy_only', 'true')
  params.set('limit', String(limit))
  params.set('offset', String(offset))
  const { data } = await api.get<ScreenerPage>('/api/screener', { params })
  return data
}

export interface SyncStart {
  running: boolean
  queued: number
  total: number
  remaining: number
}

export async function fetchSyncStatus(): Promise<SyncStatus> {
  const { data } = await api.get<SyncStatus>('/api/screener/sync/status')
  return data
}

export async function startScreenerSync(
  opts: { limit?: number; all?: boolean } = {},
): Promise<SyncStart> {
  const params: Record<string, string | number> = {}
  if (opts.limit) params.limit = opts.limit
  if (opts.all) params.all = 'true'
  const { data } = await api.post<SyncStart>('/api/screener/sync', null, { params })
  return data
}

export async function cancelScreenerSync(): Promise<SyncStatus> {
  const { data } = await api.post<SyncStatus>('/api/screener/sync/cancel')
  return data
}
