import { lazy, Suspense, useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowDownRight,
  ArrowUpRight,
  CandlestickChart,
  LineChart,
  Star,
} from 'lucide-react'
import {
  addToWatchlist,
  fetchFundamentals,
  removeFromWatchlist,
  type ChartSpan,
} from '../api'
import {
  queryKeys,
  useCompany,
  useDividends,
  useFundamentals,
  useHistory,
  useIndexHistory,
  useRecommendation,
  useValuation,
  useWatchlist,
} from '../hooks'
import { fmtChange, fmtPct, fmtPercent, fmtPrice, fmtRatio } from '../lib/format'
import { useSettings } from '../lib/settings'
import { SPANS, spanStart } from '../lib/spans'
import BoardBadge from './BoardBadge'
import Modal from './Modal'
import CompanyPanel from './CompanyPanel'
import FundamentalsPanel from './FundamentalsPanel'
import RecommendationPanel from './RecommendationPanel'
import SubTabs from './SubTabs'

// lightweight-charts is heavy; load it only when a chart is actually shown.
import type { Indicators } from './StockChart'
const StockChart = lazy(() => import('./StockChart'))

// Minimal shape needed to render the modal — both Stock and WatchlistItem fit.
export interface StockLike {
  ticker: string
  name: string
  indices: string[]
  last_price: number | null
  change?: number | null
  change_percent?: number | null
  board?: string | null
}

type Tab = 'chart' | 'fundamentals' | 'recommendation' | 'company'
type FinTab = 'financials' | 'valuation' | 'dividends'
type CompanyTab = 'overview' | 'board'

export default function StockDetailModal({
  stock,
  onClose,
  initialTab = 'chart',
}: {
  stock: StockLike
  onClose: () => void
  initialTab?: Tab
}) {
  const [tab, setTab] = useState<Tab>(initialTab)
  const [finTab, setFinTab] = useState<FinTab>('financials')
  const [companyTab, setCompanyTab] = useState<CompanyTab>('overview')
  const { settings } = useSettings()
  const [range, setRange] = useState<'1d' | '1m'>(settings.chartRange)
  const [span, setSpan] = useState<ChartSpan>('1y')
  const [chartType, setChartType] = useState<'candle' | 'line'>(settings.chartType)
  const [ind, setInd] = useState<Indicators>({
    ma20: false,
    ma50: false,
    ma200: false,
    volume: true,
    rsi: false,
  })
  const queryClient = useQueryClient()

  // --- Chart data -----------------------------------------------------------
  const history = useHistory(stock.ticker, range, span, tab === 'chart')
  // Benchmark overlay: IHSG daily bars for the same span (daily view only).
  const [vsIhsg, setVsIhsg] = useState(false)
  const ihsg = useIndexHistory(
    'COMPOSITE',
    span,
    tab === 'chart' && vsIhsg && range === '1d',
  )
  const splitMarkers = useMemo(
    () =>
      range === '1d'
        ? (history.data?.splits ?? []).map((s) => ({
            date: s.ex_date,
            text: `Split ${s.ratio >= 1 ? `${s.ratio}:1` : `1:${Math.round(1 / s.ratio)}`}`,
          }))
        : undefined,
    [range, history.data?.splits],
  )
  const compare = useMemo(
    () =>
      vsIhsg && range === '1d' && ihsg.data
        ? { label: 'IHSG', points: ihsg.data.points }
        : undefined,
    [vsIhsg, range, ihsg.data],
  )
  const visibleFrom = range === '1d' ? spanStart(span) : undefined

  // --- Fundamentals (fetched per sub-tab, cached) ---------------------------
  const onFin = tab === 'fundamentals'
  const fundamentals = useFundamentals(stock.ticker, onFin && finTab === 'financials')
  const valuation = useValuation(stock.ticker, onFin && finTab === 'valuation')
  const dividends = useDividends(stock.ticker, onFin && finTab === 'dividends')
  const refreshFundamentals = useMutation({
    mutationFn: () => fetchFundamentals(stock.ticker, true),
    onSuccess: (data) =>
      queryClient.setQueryData(queryKeys.fundamentals(stock.ticker), data),
  })

  // --- Recommendation (cross-sectional score) -------------------------------
  const recommendation = useRecommendation(stock.ticker, tab === 'recommendation')

  // --- Company profile ------------------------------------------------------
  const company = useCompany(stock.ticker, tab === 'company')

  // --- Watchlist toggle (self-contained) ------------------------------------
  const watchlist = useWatchlist()
  const watched = (watchlist.data ?? []).some((w) => w.ticker === stock.ticker)
  const invalidateWatch = () => queryClient.invalidateQueries({ queryKey: ['watchlist'] })
  const add = useMutation({
    mutationFn: () => addToWatchlist(stock.ticker),
    onSuccess: invalidateWatch,
  })
  const remove = useMutation({
    mutationFn: () => removeFromWatchlist(stock.ticker),
    onSuccess: invalidateWatch,
  })
  const watchPending = add.isPending || remove.isPending

  const up = (stock.change ?? stock.change_percent ?? 0) >= 0
  const tone = !settings.colorizeChanges ? 'text-muted' : up ? 'text-bull' : 'text-bear'
  const seg = (active: boolean) =>
    `px-2.5 py-1 text-xs transition ${
      active ? 'bg-active text-ink' : 'text-muted hover:text-ink'
    }`

  return (
    <Modal
      label={`${stock.ticker} ${stock.name}`}
      onClose={onClose}
      // Tabs stay put; only the tab content scrolls.
      bodyClassName="flex flex-col"
      header={
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">{stock.ticker}</h2>
            <BoardBadge board={stock.board} />
            {stock.indices.map((idx) => (
              <span
                key={idx}
                className="rounded-sm bg-panelalt px-1.5 py-0.5 text-[10px] text-muted"
              >
                {idx}
              </span>
            ))}
          </div>
          <p className="text-xs text-muted">{stock.name}</p>
          <div className="mt-1.5 flex items-baseline gap-3">
            <span className="text-xl font-bold">{fmtPrice(stock.last_price)}</span>
            {stock.change_percent != null && (
              <span className={`flex items-center text-xs font-medium ${tone}`}>
                {up ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
                {stock.change != null && <>{fmtChange(stock.change)} </>}(
                {fmtPct(stock.change_percent)})
              </span>
            )}
          </div>
        </div>
      }
      actions={
        <button
          onClick={() => (watched ? remove.mutate() : add.mutate())}
          disabled={watchPending}
          title={watched ? 'Remove from watchlist' : 'Add to watchlist'}
          className={`flex items-center gap-1 rounded px-2.5 py-1.5 text-xs font-medium ring-1 transition disabled:opacity-50 ${
            watched
              ? 'text-accent ring-accent/40 hover:bg-accent/10'
              : 'text-muted ring-line-strong hover:bg-panelalt hover:text-ink'
          }`}
        >
          <Star size={14} className={watched ? 'fill-current' : ''} />
          {watched ? 'Watching' : 'Watch'}
        </button>
      }
    >
      {/* Tabs */}
      <div className="shrink-0">
        <div className="flex w-fit gap-1 rounded-md bg-panelalt/70 p-1 ring-1 ring-line-strong">
          <button
            onClick={() => setTab('chart')}
            className={`rounded px-3 py-1.5 text-xs font-medium transition ${
              tab === 'chart'
                ? 'bg-panel text-ink shadow-card ring-1 ring-line-strong'
                : 'text-muted hover:text-ink'
            }`}
          >
            Chart
          </button>
          <button
            onClick={() => setTab('fundamentals')}
            className={`rounded px-3 py-1.5 text-xs font-medium transition ${
              tab === 'fundamentals'
                ? 'bg-panel text-ink shadow-card ring-1 ring-line-strong'
                : 'text-muted hover:text-ink'
            }`}
          >
            Fundamentals
          </button>
          <button
            onClick={() => setTab('recommendation')}
            className={`rounded px-3 py-1.5 text-xs font-medium transition ${
              tab === 'recommendation'
                ? 'bg-panel text-ink shadow-card ring-1 ring-line-strong'
                : 'text-muted hover:text-ink'
            }`}
          >
            Signal
          </button>
          <button
            onClick={() => setTab('company')}
            className={`rounded px-3 py-1.5 text-xs font-medium transition ${
              tab === 'company'
                ? 'bg-panel text-ink shadow-card ring-1 ring-line-strong'
                : 'text-muted hover:text-ink'
            }`}
          >
            Company
          </button>
        </div>
      </div>

      {/* Scrollable content region — header + tabs stay pinned */}
      <div className="mt-3 min-h-0 flex-1 overflow-y-auto pr-1">
        {/* Chart tab */}
        {tab === 'chart' && (
          <>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <div className="flex overflow-hidden rounded ring-1 ring-line-strong">
                {(['1d', '1m'] as const).map((i) => (
                  <button
                    key={i}
                    onClick={() => setRange(i)}
                    className={seg(range === i)}
                  >
                    {i === '1d' ? 'Daily' : '1-Min'}
                  </button>
                ))}
              </div>
              {range === '1d' && (
                <div
                  className="flex overflow-hidden rounded ring-1 ring-line-strong"
                  role="group"
                  aria-label="Time span"
                >
                  {SPANS.map((s) => (
                    <button
                      key={s.value}
                      onClick={() => setSpan(s.value)}
                      aria-pressed={span === s.value}
                      className={seg(span === s.value)}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              )}
              <div className="flex overflow-hidden rounded ring-1 ring-line-strong">
                <button
                  onClick={() => setChartType('line')}
                  className={`flex items-center gap-1 ${seg(chartType === 'line')}`}
                >
                  <LineChart size={13} /> Line
                </button>
                <button
                  onClick={() => setChartType('candle')}
                  className={`flex items-center gap-1 ${seg(chartType === 'candle')}`}
                >
                  <CandlestickChart size={13} /> Candle
                </button>
              </div>
              <div className="flex flex-wrap gap-1">
                {(
                  [
                    ['ma20', 'MA20'],
                    ['ma50', 'MA50'],
                    ['ma200', 'MA200'],
                    ['volume', 'Vol'],
                    ['rsi', 'RSI'],
                  ] as const
                ).map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => setInd((s) => ({ ...s, [key]: !s[key] }))}
                    className={`rounded px-2 py-1 text-[11px] font-medium ring-1 transition ${
                      ind[key]
                        ? 'bg-accent/15 text-accent ring-accent/30'
                        : 'text-muted ring-line-strong hover:bg-panelalt hover:text-ink'
                    }`}
                  >
                    {label}
                  </button>
                ))}
                {range === '1d' && (
                  <button
                    onClick={() => setVsIhsg((v) => !v)}
                    aria-pressed={vsIhsg}
                    title="Compare with IHSG: both lines in % change from the left edge of the chart"
                    className={`rounded px-2 py-1 text-[11px] font-medium ring-1 transition ${
                      vsIhsg
                        ? 'bg-accent/15 text-accent ring-accent/30'
                        : 'text-muted ring-line-strong hover:bg-panelalt hover:text-ink'
                    }`}
                  >
                    vs IHSG
                  </button>
                )}
              </div>
            </div>

            <div className="mt-3">
              {history.isFetching && !history.isLoading && (
                <p className="mb-1 text-[11px] text-subtle" aria-live="polite">
                  {span === '5y' || span === 'max'
                    ? 'Loading full price history (first time can take a few seconds)…'
                    : 'Updating…'}
                </p>
              )}
              {history.isLoading ? (
                <div className="flex h-[400px] items-center justify-center text-muted">
                  Loading chart…
                </div>
              ) : history.data && history.data.points.length > 0 ? (
                <Suspense
                  fallback={
                    <div className="flex h-[400px] items-center justify-center text-muted">
                      Loading chart…
                    </div>
                  }
                >
                  <StockChart
                    data={history.data.points}
                    chartType={chartType}
                    indicators={ind}
                    visibleFrom={visibleFrom}
                    compare={compare}
                    markers={splitMarkers}
                  />
                </Suspense>
              ) : (
                <div className="flex h-[400px] items-center justify-center text-muted">
                  No price data yet for this interval.
                </div>
              )}
            </div>
          </>
        )}

        {/* Fundamentals tab */}
        {tab === 'fundamentals' && (
          <div className="mt-3 space-y-3">
            <SubTabs<FinTab>
              options={[
                { value: 'financials', label: 'Financials' },
                { value: 'valuation', label: 'Valuation' },
                { value: 'dividends', label: 'Dividends' },
              ]}
              value={finTab}
              onChange={setFinTab}
            />

            {finTab === 'financials' && (
              <FundamentalsPanel
                data={fundamentals.data}
                isLoading={fundamentals.isLoading}
                isError={fundamentals.isError}
                onRefresh={() => refreshFundamentals.mutate()}
                isRefreshing={refreshFundamentals.isPending}
              />
            )}

            {finTab === 'valuation' &&
              (valuation.data &&
              (valuation.data.pbv != null || valuation.data.roe != null) ? (
                <div className="surface p-4">
                  <div className="mb-3 text-[10px] uppercase tracking-wider text-muted">
                    Relative valuation
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2">
                    {[
                      {
                        label: 'PBV',
                        value: valuation.data.pbv,
                        range: `${valuation.data.pbv_min ?? '—'} – ${valuation.data.pbv_max ?? '—'}`,
                        pct: valuation.data.pbv_percentile,
                        window: `${valuation.data.window_days}d`,
                      },
                      {
                        label: 'RoE',
                        value: valuation.data.roe,
                        range: `${valuation.data.years.length} yrs`,
                        pct: valuation.data.roe_percentile,
                        window: 'history',
                      },
                    ].map((row) => (
                      <div key={row.label} className="text-xs">
                        <div className="flex items-baseline justify-between">
                          <span className="text-muted">
                            {row.label}{' '}
                            <span className="font-medium text-ink">
                              {row.label === 'PBV'
                                ? fmtRatio(row.value)
                                : fmtPercent(row.value)}
                            </span>
                          </span>
                          <span className="text-[10px] text-subtle">{row.range}</span>
                        </div>
                        <div className="mt-1.5 h-1.5 overflow-hidden rounded-sm bg-panelalt">
                          <div
                            className="h-full rounded-sm bg-accent"
                            style={{ width: `${row.pct ?? 0}%` }}
                          />
                        </div>
                        <div className="mt-1 text-[10px] text-subtle">
                          {row.pct != null ? `${row.pct.toFixed(0)}th percentile` : '—'} ·
                          vs {row.window}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="py-10 text-center text-sm text-muted">
                  {valuation.isLoading
                    ? 'Loading valuation…'
                    : 'No valuation data available.'}
                </div>
              ))}

            {finTab === 'dividends' &&
              (dividends.data && dividends.data.history.length > 0 ? (
                <div className="surface p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <span className="text-[10px] uppercase tracking-wider text-muted">
                      Dividends
                    </span>
                    <span className="text-xs text-muted">
                      Trailing DPS{' '}
                      <span className="font-medium text-ink">
                        {fmtPrice(dividends.data.trailing_dps)}
                      </span>
                      {dividends.data.yield_percent != null && (
                        <>
                          {' · yield '}
                          <span className="font-medium text-bull">
                            {dividends.data.yield_percent.toFixed(2)}%
                          </span>
                        </>
                      )}
                    </span>
                  </div>
                  <ul className="divide-y divide-line text-xs">
                    {dividends.data.history.slice(0, 8).map((d) => (
                      <li key={d.ex_date} className="flex justify-between py-1.5">
                        <span className="text-muted">{d.ex_date}</span>
                        <span className="tabular-nums text-ink">
                          {fmtPrice(d.amount)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <div className="py-10 text-center text-sm text-muted">
                  {dividends.isLoading
                    ? 'Loading dividends…'
                    : 'No dividend history available.'}
                </div>
              ))}
          </div>
        )}

        {/* Recommendation tab */}
        {tab === 'recommendation' && (
          <div className="mt-3">
            <RecommendationPanel
              data={recommendation.data}
              isLoading={recommendation.isLoading}
              isError={recommendation.isError}
            />
          </div>
        )}

        {/* Company tab */}
        {tab === 'company' && (
          <div className="mt-3 space-y-3">
            <SubTabs<CompanyTab>
              options={[
                { value: 'overview', label: 'Overview' },
                { value: 'board', label: 'Board' },
              ]}
              value={companyTab}
              onChange={setCompanyTab}
            />
            <CompanyPanel
              data={company.data}
              isLoading={company.isLoading}
              isError={company.isError}
              section={companyTab}
            />
          </div>
        )}
      </div>
    </Modal>
  )
}
