import axios from 'axios'

// Configurable via VITE_API_URL (set in docker-compose / .env). Falls back to
// localhost for running `npm run dev` outside Docker.
const baseURL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export const api = axios.create({ baseURL, timeout: 15_000 })

// Mirror of the backend INDEX_ORDER. Used as a fallback so the selector is
// always fully populated, even before/if the /api/indexes request resolves.
export const DEFAULT_INDEXES = [
  'LQ45',
  'IDX30',
  'JII',
  'ISSI',
  'IDXHIDIV20',
  'IDXBUMN20',
]

export interface Stock {
  id: number
  ticker: string
  name: string
  indices: string[]
  last_price: number | null
  previous_close: number | null
  change: number | null
  change_percent: number | null
  volume: number | null
  updated_at: string | null
}

export interface PricePoint {
  timestamp: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface StockHistory {
  ticker: string
  name: string
  indices: string[]
  interval: string
  points: PricePoint[]
}

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

// --------------------------------------------------------------------------- //
// Watchlist + fundamentals
// --------------------------------------------------------------------------- //

export interface Fundamental {
  fiscal_year: number
  financial_currency: string | null
  total_shares: number | null
  revenue: number | null
  net_income: number | null
  total_assets: number | null
  total_liabilities: number | null
  equity: number | null
}

export interface DerivedMetrics {
  market_cap: number | null
  book_value: number | null
  pbv: number | null
  roe: number | null
}

export interface WatchlistItem {
  id: number
  ticker: string
  name: string
  indices: string[]
  added_at: string | null
  last_price: number | null
  change_percent: number | null
  fundamental: Fundamental | null
  metrics: DerivedMetrics
}

export interface FundamentalsResponse {
  ticker: string
  name: string
  yearly: Fundamental[]
  latest: Fundamental | null
  metrics: DerivedMetrics
}

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

export async function fetchFundamentals(
  ticker: string,
): Promise<FundamentalsResponse> {
  const { data } = await api.get<FundamentalsResponse>(
    `/api/stocks/${ticker}/fundamentals`,
  )
  return data
}
