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
  recommendation: RecommendationSummary | null
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

export interface MarketStatus {
  is_open: boolean
  session: 'pre_open' | 'open' | 'break' | 'closed'
  timezone: string
  server_time: string
  next_change_at: string | null
  next_change_label: string
}

// --- Portfolio -------------------------------------------------------------

export interface Transaction {
  id: number
  ticker: string
  side: 'buy' | 'sell'
  quantity: number
  price: number
  fees: number
  trade_date: string
  note: string | null
}

export interface TransactionInput {
  ticker: string
  side: 'buy' | 'sell'
  quantity: number
  price: number
  fees?: number
  trade_date: string
  note?: string | null
}

export interface Holding {
  ticker: string
  name: string
  quantity: number
  avg_cost: number
  price: number | null
  market_value: number | null
  invested: number
  unrealized_pl: number | null
  unrealized_pl_pct: number | null
  day_change: number | null
  day_change_pct: number | null
  weight: number | null
  projected_income: number | null
}

export interface PortfolioTotals {
  invested: number
  market_value: number
  unrealized_pl: number
  unrealized_pl_pct: number | null
  day_change: number
  day_change_pct: number | null
  realized_pl: number
  projected_income: number
}

export interface Portfolio {
  totals: PortfolioTotals
  holdings: Holding[]
}

export interface EquityPoint {
  date: string
  value: number
}

// --- Screener / search / market overview -----------------------------------

export interface ScreenerRow {
  ticker: string
  name: string
  indices: string[]
  sector: string | null
  price: number | null
  change_percent: number | null
  pbv: number | null
  roe: number | null
  score: number | null
  rating: string | null
  strength: string | null
}

export interface SearchResult {
  symbol: string
  name: string
  exchange: string
  type: string
}

export interface Mover {
  ticker: string
  name: string
  price: number | null
  change_percent: number | null
}

export interface Sector {
  sector: string
  count: number
  avg_change_percent: number
}

export interface MarketOverview {
  up: number
  down: number
  flat: number
  top_gainers: Mover[]
  top_losers: Mover[]
  sectors: Sector[]
}

// --- Alerts ----------------------------------------------------------------

export type AlertType = 'price_above' | 'price_below' | 'pct_change' | 'rating_change'

export interface Alert {
  id: number
  ticker: string
  type: AlertType
  threshold: number | null
  active: boolean
  last_triggered_at: string | null
  created_at: string
}

export interface AlertInput {
  ticker: string
  type: AlertType
  threshold?: number | null
}

export interface AlertEvent {
  id: number
  alert_id: number
  ticker: string
  triggered_at: string
  value: number | null
  message: string
}

// --- Valuation & dividends -------------------------------------------------

export interface Valuation {
  ticker: string
  pbv: number | null
  pbv_min: number | null
  pbv_max: number | null
  pbv_percentile: number | null
  roe: number | null
  roe_percentile: number | null
  years: number[]
  window_days: number
}

export interface Dividend {
  ex_date: string
  amount: number
}

export interface DividendSummary {
  ticker: string
  trailing_dps: number
  yield_percent: number | null
  history: Dividend[]
}
