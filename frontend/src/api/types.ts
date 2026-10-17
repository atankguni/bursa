// Shared API types (mirror the backend Pydantic schemas).

export interface Stock {
  id: number
  ticker: string
  name: string
  /** IDX listing board; 'Watchlist' = special monitoring (Papan Pemantauan Khusus). */
  board?: string | null
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
  /** Stock splits (ratio = new shares per old share), for chart markers. */
  splits?: { ex_date: string; ratio: number }[]
}

/** Chart span for daily bars; 5y/max load the stock's full history on first use. */
export type ChartSpan = '1m' | '3m' | '6m' | '1y' | '5y' | 'max'

/** An IDX stock index (indeks saham) with its latest value. */
export interface MarketIndex {
  code: string
  name: string
  group: string
  last: number | null
  previous_close: number | null
  change: number | null
  change_percent: number | null
  updated_at: string | null
  /** Provider has full history; otherwise it builds up daily from `history_since`. */
  has_history: boolean
  history_since: string | null
}

export interface IndexHistory {
  code: string
  name: string
  has_history: boolean
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
  /** 'statements' (yearly tables) or 'summary' (Yahoo summary; latest only, TTM). */
  source?: string | null
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
  /** IDX listing board; 'Watchlist' = special monitoring (Papan Pemantauan Khusus). */
  board?: string | null
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

/** Long-term fundamentals vs short-term (swing, 1-4 weeks) price action. */
export type InvestingStyle = 'investor' | 'trader'

// --- AI assistant ------------------------------------------------------------

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
}

export interface AssistantReply {
  reply: string
  provider: string
  model: string
  tools_used: string[]
  remaining_today: number
  /** The saved chat this answer went into; null when the user doesn't save chats. */
  chat_id: number | null
}

export interface AssistantStatus {
  configured: boolean
  models: string[]
  setup_hint: string
  personal_data: boolean
  remaining_today: number
  daily_limit: number
  save_chats: boolean
  /** Saved chats are deleted this many days after their last message. */
  chat_days: number
}

export interface ChatSummary {
  id: number
  /** The first question. */
  title: string
  created_at: string
  /** Time of the last message. */
  updated_at: string
}

export interface SavedChatMessage extends ChatTurn {
  tools_used: string[] | null
  created_at: string
}

export interface ChatDetail extends ChatSummary {
  messages: SavedChatMessage[]
}

/** The Settings-menu options saved per user (they follow you across devices). */
export interface DisplaySettings {
  defaultIndexes: string[]
  chartType: 'candle' | 'line'
  chartRange: '1d' | '1m'
  autoRefresh: boolean
  refreshSeconds: number
  numberFormat: 'compact' | 'full'
  colorizeChanges: boolean
  hiddenColumns: { home: string[]; watchlist: string[] }
}

export interface Preferences {
  investing_style: InvestingStyle
  /** Opt-in: the AI assistant may read the watchlist and portfolio. */
  assistant_personal_data: boolean
  /** Keep assistant chats so they can be continued (deleted after a few days). */
  assistant_save_chats: boolean
  /** null until first saved: the browser then uploads what it had. */
  display: DisplaySettings | null
  /** Alert events up to this (server) time were seen: the bell's unread count. */
  alerts_seen_at: string | null
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
  style: InvestingStyle
}

export interface MarketStatus {
  is_open: boolean
  session: 'pre_open' | 'open' | 'break' | 'closed'
  timezone: string
  server_time: string
  next_change_at: string | null
  next_change_label: string
}

export interface Status {
  server_time: string
  timezone: string
  session: 'pre_open' | 'open' | 'break' | 'closed'
  last_sync: string | null
  stocks_tracked: number
  providers: Record<string, string>
  calls_today: Record<string, number>
  lot_size: number
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
  board?: string | null
  /** Some trades were re-expressed in post-split shares. */
  split_adjusted?: boolean
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

/** A projected (not announced) dividend, from last year's ex-date. */
export interface ExpectedDividend {
  ticker: string
  name: string
  expected_ex_date: string
  based_on: string
  amount_per_share: number
  regular: boolean
  shares_held: number | null
  expected_income: number | null
  in_portfolio: boolean
  in_watchlist: boolean
}

export interface PortfolioRisk {
  holdings: { ticker: string; weight: number; sector: string; beta: number | null }[]
  sectors: { sector: string; weight: number }[]
  effective_holdings: number | null
  top_weight: number | null
  top3_weight: number | null
  beta: number | null
  stress_ihsg_pct: number
  stress_portfolio_pct: number | null
  last_day_portfolio_pct: number | null
  last_day_ihsg_pct: number | null
  max_drawdown_pct: number | null
  warnings: string[]
}

export interface EquityPoint {
  date: string
  value: number
  /** Cumulative time-weighted return (%), with deposits/withdrawals taken out. */
  return_pct: number | null
  /** IHSG's cumulative change (%) over the same days. */
  benchmark_pct: number | null
}

// --- Screener / search / market overview -----------------------------------

export interface ScreenerRow {
  ticker: string
  name: string
  board?: string | null
  indices: string[]
  sector: string | null
  price: number | null
  change_percent: number | null
  pbv: number | null
  roe: number | null
  score: number | null
  rating: string | null
  strength: string | null
  has_fundamentals: boolean
}

export interface ScreenerPage {
  items: ScreenerRow[]
  total: number
  limit: number
  offset: number
}

export interface SyncStatus {
  running: boolean
  /** 'batch' = one capped run; 'all' = paced batches until every stock is tried. */
  mode: 'batch' | 'all'
  /** What the job is doing now, e.g. "Pausing 60s between batches". */
  note: string | null
  total: number
  done: number
  remaining: number
  last_error: string | null
  missing: number
}

export interface CatalogRow {
  ticker: string
  name: string
  board?: string | null
  tracked: boolean
  indices: string[]
  last_price: number | null
  change_percent: number | null
}

export interface CatalogPage {
  items: CatalogRow[]
  total: number
  limit: number
  offset: number
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

export interface Officer {
  name: string
  title: string | null
}

export interface Company {
  ticker: string
  name: string
  sector: string | null
  industry: string | null
  description: string | null
  employees: number | null
  website: string | null
  country: string | null
  city: string | null
  address: string | null
  phone: string | null
  officers: Officer[]
}
