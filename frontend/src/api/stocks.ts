import { api } from './client'
import type { FundamentalsResponse, Recommendation, Stock, StockHistory } from './types'

export async function fetchIndexes(): Promise<string[]> {
  const { data } = await api.get<string[]>('/api/indexes')
  return data
}

export async function fetchStocks(indexes?: string[]): Promise<Stock[]> {
  // Repeated `index` params (index=LQ45&index=IDX30); FastAPI reads them as a list.
  const params = new URLSearchParams()
  indexes?.forEach((i) => params.append('index', i))
  const { data } = await api.get<Stock[]>('/api/stocks', { params })
  return data
}

export async function fetchHistory(
  ticker: string,
  interval: '1d' | '1m' = '1d',
): Promise<StockHistory> {
  const { data } = await api.get<StockHistory>(`/api/stocks/${ticker}/history`, {
    params: { interval },
  })
  return data
}

export async function fetchFundamentals(
  ticker: string,
  refresh = false,
): Promise<FundamentalsResponse> {
  const { data } = await api.get<FundamentalsResponse>(
    `/api/stocks/${ticker}/fundamentals`,
    { params: refresh ? { refresh: true } : undefined },
  )
  return data
}

export async function fetchRecommendation(ticker: string): Promise<Recommendation> {
  const { data } = await api.get<Recommendation>(`/api/stocks/${ticker}/recommendation`)
  return data
}
