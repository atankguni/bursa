import { api } from './client'
import type { WatchlistItem } from './types'

export async function fetchWatchlist(): Promise<WatchlistItem[]> {
  const { data } = await api.get<WatchlistItem[]>('/api/watchlist')
  return data
}

export async function addToWatchlist(ticker: string): Promise<WatchlistItem> {
  const { data } = await api.post<WatchlistItem>(`/api/watchlist/${ticker}`)
  return data
}

export async function removeFromWatchlist(ticker: string): Promise<void> {
  await api.delete(`/api/watchlist/${ticker}`)
}

export async function refreshWatchlist(): Promise<{ tickers: number; rows: number }> {
  const { data } = await api.post<{ tickers: number; rows: number }>(
    '/api/watchlist/refresh',
  )
  return data
}
