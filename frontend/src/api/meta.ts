import { api } from './client'
import type { MarketStatus } from './types'

export async function fetchMarketStatus(): Promise<MarketStatus> {
  const { data } = await api.get<MarketStatus>('/api/market-status')
  return data
}
