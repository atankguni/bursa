import axios from 'axios'

// Configurable via VITE_API_URL (set in docker-compose / .env). Falls back to
// localhost for running `npm run dev` outside Docker.
const baseURL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export const api = axios.create({ baseURL, timeout: 15_000 })

export interface Stock {
  id: number
  ticker: string
  name: string
  index_name: string
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
  index_name: string
  interval: string
  points: PricePoint[]
}

export async function fetchStocks(): Promise<Stock[]> {
  const { data } = await api.get<Stock[]>('/api/stocks')
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
