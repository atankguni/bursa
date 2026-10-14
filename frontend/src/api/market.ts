import { api } from './client'
import type { MarketOverview } from './types'

export async function fetchMarketOverview(): Promise<MarketOverview> {
  const { data } = await api.get<MarketOverview>('/api/market/overview')
  return data
}
