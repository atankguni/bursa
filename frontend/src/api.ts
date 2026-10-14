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

export async function fetchStocks(index?: string): Promise<Stock[]> {
  const { data } = await api.get<Stock[]>('/api/stocks', {
    params: index ? { index } : undefined,
  })
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
