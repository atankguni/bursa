import { api } from './client'
import type { MarketStatus, Status } from './types'

export async function fetchMarketStatus(): Promise<MarketStatus> {
  const { data } = await api.get<MarketStatus>('/api/market-status')
  return data
}

export async function fetchStatus(): Promise<Status> {
  const { data } = await api.get<Status>('/api/status')
  return data
}
