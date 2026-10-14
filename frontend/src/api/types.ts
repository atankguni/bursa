// Shared API types (mirror the backend Pydantic schemas).

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
  recommendation: RecommendationSummary | null
}

export interface FundamentalsResponse {
  ticker: string
  name: string
  yearly: Fundamental[]
  latest: Fundamental | null
  metrics: DerivedMetrics
}

// --- Recommendation --------------------------------------------------------

export interface Category {
  name: string
  weight: number
  score: number | null
}

export interface RecommendationSummary {
  score: number
  rating: string
  strength: string
}

export interface Recommendation {
  ticker: string
  score: number
  rating: string
  strength: string
  coverage: number
  categories: Category[]
  reasons: string[]
  disclaimer: string
}
