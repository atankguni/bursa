import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  CandlestickChart,
  ChevronDown,
  LineChart,
  RefreshCw,
  TrendingDown,
  TrendingUp,
  X,
} from 'lucide-react'
import {
  DEFAULT_INDEXES,
  fetchHistory,
  fetchIndexes,
  fetchStocks,
  type Stock,
} from './api'
import StockChart from './components/StockChart'

// --------------------------------------------------------------------------- //
// Formatting helpers
// --------------------------------------------------------------------------- //

const fmtPrice = (v: number | null) =>
  v == null
    ? '—'
    : new Intl.NumberFormat('id-ID', { maximumFractionDigits: 2 }).format(v)

const fmtVolume = (v: number | null) => {
  if (v == null) return '—'
  if (v >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(2)}M`
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(2)}jt`
  if (v >= 1_000) return `${(v / 1_000).toFixed(1)}rb`
  return String(v)
}

const fmtChange = (v: number | null) => (v == null ? '' : `${v > 0 ? '+' : ''}${v.toFixed(2)}`)
const fmtPct = (v: number | null) => (v == null ? '' : `${v > 0 ? '+' : ''}${v.toFixed(2)}%`)

// --------------------------------------------------------------------------- //
// Detail modal (chart)
// --------------------------------------------------------------------------- //

function StockDetail({ stock, onClose }: { stock: Stock; onClose: () => void }) {
  const [range, setRange] = useState<'1d' | '1m'>('1d')
  const [chartType, setChartType] = useState<'candle' | 'line'>('candle')

  const { data, isLoading } = useQuery({
    queryKey: ['history', stock.ticker, range],
    queryFn: () => fetchHistory(stock.ticker, range),
  })

  const up = (stock.change ?? 0) >= 0
  const tone = up ? 'text-bull' : 'text-bear'

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-4xl rounded-2xl bg-panel p-6 shadow-2xl ring-1 ring-slate-700"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-semibold">{stock.ticker}</h2>
              {stock.indices.map((idx) => (
                <span
                  key={idx}
                  className="rounded bg-panelalt px-2 py-0.5 text-xs text-slate-300"
                >
                  {idx}
                </span>
              ))}
            </div>
            <p className="text-sm text-slate-400">{stock.name}</p>
            <div className="mt-2 flex items-baseline gap-3">
              <span className="text-2xl font-bold">{fmtPrice(stock.last_price)}</span>
              <span className={`flex items-center text-sm font-medium ${tone}`}>
                {up ? <ArrowUpRight size={16} /> : <ArrowDownRight size={16} />}
                {fmtChange(stock.change)} ({fmtPct(stock.change_percent)})
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-slate-400 transition hover:bg-panelalt hover:text-white"
            aria-label="Close"
          >
            <X size={20} />
          </button>
        </div>

        {/* Controls */}
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <div className="flex overflow-hidden rounded-lg ring-1 ring-slate-700">
            {(['1d', '1m'] as const).map((i) => (
              <button
                key={i}
                onClick={() => setRange(i)}
                className={`px-3 py-1.5 text-sm ${
                  range === i ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-white'
                }`}
              >
                {i === '1d' ? 'Daily' : '1-Min'}
              </button>
            ))}
          </div>
          <div className="flex overflow-hidden rounded-lg ring-1 ring-slate-700">
            <button
              onClick={() => setChartType('candle')}
              className={`flex items-center gap-1 px-3 py-1.5 text-sm ${
                chartType === 'candle' ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-white'
              }`}
            >
              <CandlestickChart size={14} /> Candle
            </button>
            <button
              onClick={() => setChartType('line')}
              className={`flex items-center gap-1 px-3 py-1.5 text-sm ${
                chartType === 'line' ? 'bg-slate-700 text-white' : 'text-slate-400 hover:text-white'
              }`}
            >
              <LineChart size={14} /> Line
            </button>
          </div>
        </div>

        {/* Chart */}
        <div className="mt-4">
          {isLoading ? (
            <div className="flex h-[420px] items-center justify-center text-slate-500">
              Loading chart…
            </div>
          ) : data && data.points.length > 0 ? (
            <StockChart data={data.points} chartType={chartType} />
          ) : (
            <div className="flex h-[420px] items-center justify-center text-slate-500">
              No price data yet for this interval.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// --------------------------------------------------------------------------- //
// Main dashboard
// --------------------------------------------------------------------------- //

export default function App() {
  // Default index on every load is LQ45; user can switch via the header select.
  const [index, setIndex] = useState('LQ45')
  const [selected, setSelected] = useState<Stock | null>(null)

  const { data: serverIndexes } = useQuery({
    queryKey: ['indexes'],
    queryFn: fetchIndexes,
  })

  // Prefer the server list; fall back to the built-in list until it resolves.
  const indexes =
    serverIndexes && serverIndexes.length > 0 ? serverIndexes : DEFAULT_INDEXES

  const {
    data: stocks = [],
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ['stocks', index],
    queryFn: () => fetchStocks(index),
  })

  // Aggregate market breadth for the summary header bar.
  const summary = useMemo(() => {
    let gainers = 0
    let losers = 0
    let unchanged = 0
    for (const s of stocks) {
      if (s.change_percent == null) unchanged++
      else if (s.change_percent > 0) gainers++
      else if (s.change_percent < 0) losers++
      else unchanged++
    }
    const updated = stocks.find((s) => s.updated_at)?.updated_at ?? null
    return { gainers, losers, unchanged, updated }
  }, [stocks])

  const marketUp = summary.gainers >= summary.losers

  return (
    <div className="min-h-full bg-slate-950">
      {/* Summary header bar */}
      <header className="sticky top-0 z-10 border-b border-slate-800 bg-panel/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-bull/10 p-2 text-bull">
              <Activity size={22} />
            </div>
            <div>
              <h1 className="text-lg font-bold leading-tight">Bursa</h1>
              <p className="text-xs text-slate-400">IDX Monitor · {index}</p>
            </div>
            {/* Index selector — defaults to LQ45 on every page load. */}
            <div className="relative ml-2">
              <select
                value={index}
                onChange={(e) => {
                  setIndex(e.target.value)
                  setSelected(null)
                }}
                className="appearance-none rounded-lg bg-panelalt py-1.5 pl-3 pr-8 text-sm text-slate-100 ring-1 ring-slate-700 outline-none transition hover:bg-slate-700 focus:ring-bull"
                aria-label="Select index"
              >
                {indexes.map((idx) => (
                  <option key={idx} value={idx}>
                    {idx}
                  </option>
                ))}
              </select>
              <ChevronDown
                size={14}
                className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-slate-400"
              />
            </div>
          </div>

          <div className="flex items-center gap-6 text-sm">
            <div className="flex items-center gap-1.5">
              {marketUp ? (
                <TrendingUp size={16} className="text-bull" />
              ) : (
                <TrendingDown size={16} className="text-bear" />
              )}
              <span className={marketUp ? 'text-bull' : 'text-bear'}>
                {marketUp ? 'Market Bullish' : 'Market Bearish'}
              </span>
            </div>
            <div className="hidden items-center gap-3 sm:flex">
              <span className="text-bull">{summary.gainers} up</span>
              <span className="text-bear">{summary.losers} down</span>
              <span className="text-slate-500">{summary.unchanged} flat</span>
            </div>
            <button
              onClick={() => refetch()}
              className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-slate-300 ring-1 ring-slate-700 transition hover:bg-panelalt hover:text-white"
            >
              <RefreshCw size={14} className={isFetching ? 'animate-spin' : ''} />
              Refresh
            </button>
          </div>
        </div>
      </header>

      {/* Stocks table */}
      <main className="mx-auto max-w-6xl px-6 py-6">
        <div className="overflow-hidden rounded-xl ring-1 ring-slate-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-panelalt text-xs uppercase tracking-wide text-slate-400">
              <tr>
                <th className="px-4 py-3">Ticker</th>
                <th className="px-4 py-3">Name</th>
                <th className="px-4 py-3">Index</th>
                <th className="px-4 py-3 text-right">Last</th>
                <th className="px-4 py-3 text-right">Change</th>
                <th className="px-4 py-3 text-right">%</th>
                <th className="px-4 py-3 text-right">Volume</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {isLoading && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-slate-500">
                    Loading market data…
                  </td>
                </tr>
              )}
              {!isLoading && stocks.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-slate-500">
                    No stocks yet — the backend is still syncing.
                  </td>
                </tr>
              )}
              {stocks.map((s) => {
                const up = (s.change ?? 0) >= 0
                const tone = s.change == null ? 'text-slate-400' : up ? 'text-bull' : 'text-bear'
                return (
                  <tr
                    key={s.id}
                    onClick={() => setSelected(s)}
                    className="cursor-pointer bg-panel transition hover:bg-panelalt"
                  >
                    <td className="px-4 py-3 font-semibold">{s.ticker.replace('.JK', '')}</td>
                    <td className="px-4 py-3 text-slate-300">{s.name}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {s.indices.map((idx) => (
                          <span
                            key={idx}
                            className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300"
                          >
                            {idx}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right font-medium">{fmtPrice(s.last_price)}</td>
                    <td className={`px-4 py-3 text-right ${tone}`}>{fmtChange(s.change)}</td>
                    <td className={`px-4 py-3 text-right font-medium ${tone}`}>
                      <span className="inline-flex items-center justify-end gap-1">
                        {s.change != null &&
                          (up ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />)}
                        {fmtPct(s.change_percent)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-slate-400">{fmtVolume(s.volume)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {summary.updated && (
          <p className="mt-3 text-xs text-slate-500">
            Last sync: {new Date(summary.updated).toLocaleString('id-ID')} · auto-refresh every 60s
          </p>
        )}
      </main>

      {selected && <StockDetail stock={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
