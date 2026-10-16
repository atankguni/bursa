import { api } from './client'

export type HealthStatus = 'ok' | 'warn' | 'error'

export interface JobHealth {
  id: string
  description: string
  next_run: string | null
  last_run: string | null
  ok: boolean | null
  error: string | null
}

export interface DataHealth {
  generated_at: string
  sections: {
    jobs: { status: HealthStatus; items: JobHealth[] }
    providers: {
      status: HealthStatus
      items: {
        name: string
        calls: number
        calls_today: number
        errors: number
        last_error: string | null
      }[]
    }
    prices: {
      status: HealthStatus
      trading_day: string
      stocks: number
      current: number
      coverage_pct: number
      no_prices: number
      stale: number
      stale_sample: string[]
      intraday_tickers: number
      intraday_last: string | null
    }
    fundamentals: {
      status: HealthStatus
      statements: number
      summary: number
      missing: number
      never_tried: number
    }
    indices: {
      status: HealthStatus
      count: number
      oldest_update: string | null
      newest_update: string | null
    }
    listing: {
      status: HealthStatus
      synced_at: string | null
      boards: Record<string, number>
    }
    suspicious: {
      status: HealthStatus
      extreme_values: { ticker: string; issue: string }[]
      share_mismatches: { ticker: string; issue: string }[]
    }
  }
}

export async function fetchDataHealth(): Promise<DataHealth> {
  const { data } = await api.get<DataHealth>('/api/data-health', { timeout: 60_000 })
  return data
}
