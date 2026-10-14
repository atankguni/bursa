import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowDownRight,
  ArrowUpRight,
  Check,
  Plus,
  RefreshCw,
  TrendingDown,
  TrendingUp,
} from 'lucide-react'
import {
  DEFAULT_INDEXES,
  addToWatchlist,
  fetchIndexes,
  fetchStocks,
  fetchWatchlist,
  type Stock,
} from '../api'
import { fmtChange, fmtDateTime, fmtPct, fmtPrice, fmtVolume } from '../lib/format'
import IndexMultiSelect from '../components/IndexMultiSelect'
import StockDetailModal from '../components/StockDetailModal'

export default function Home() {
  // Default selection on every load is LQ45; user can toggle more indices.
  const [selectedIndexes, setSelectedIndexes] = useState<string[]>(['LQ45'])
  const [selected, setSelected] = useState<Stock | null>(null)
  const queryClient = useQueryClient()

  const { data: serverIndexes } = useQuery({
    queryKey: ['indexes'],
    queryFn: fetchIndexes,
  })
  const indexOptions =
    serverIndexes && serverIndexes.length > 0 ? serverIndexes : DEFAULT_INDEXES

  const {
    data: stocks = [],
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ['stocks', selectedIndexes],
    queryFn: () => fetchStocks(selectedIndexes),
  })

  // Which tickers are already on the watchlist (for the add button state).
  const { data: watchlist = [] } = useQuery({
    queryKey: ['watchlist'],
    queryFn: fetchWatchlist,
  })
  const watchSet = useMemo(
    () => new Set(watchlist.map((w) => w.ticker)),
    [watchlist],
  )

  const add = useMutation({
    mutationFn: (ticker: string) => addToWatchlist(ticker),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchlist'] })
    },
  })

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
    <main className="mx-auto max-w-6xl px-6 py-6">
      {/* Toolbar: index selector + market breadth + refresh */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-400">Indices</span>
          <IndexMultiSelect
            options={indexOptions}
            selected={selectedIndexes}
            onChange={(next) => {
              setSelectedIndexes(next)
              setSelected(null)
            }}
          />
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
              <th className="px-4 py-3 text-center">Watch</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {isLoading && (
              <tr>
                <td colSpan={8} className="px-4 py-10 text-center text-slate-500">
                  Loading market data…
                </td>
              </tr>
            )}
            {!isLoading && stocks.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-10 text-center text-slate-500">
                  No stocks match the selected indices.
                </td>
              </tr>
            )}
            {stocks.map((s) => {
              const up = (s.change ?? 0) >= 0
              const tone = s.change == null ? 'text-slate-400' : up ? 'text-bull' : 'text-bear'
              const watched = watchSet.has(s.ticker)
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
                  <td className="px-4 py-3 text-center">
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        if (!watched) add.mutate(s.ticker)
                      }}
                      disabled={watched || add.isPending}
                      title={watched ? 'On watchlist' : 'Add to watchlist'}
                      className={`inline-flex items-center justify-center rounded-lg p-1.5 transition ${
                        watched
                          ? 'cursor-default text-bull'
                          : 'text-slate-400 ring-1 ring-slate-700 hover:bg-slate-700 hover:text-white'
                      }`}
                    >
                      {watched ? <Check size={15} /> : <Plus size={15} />}
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {summary.updated && (
        <p className="mt-3 text-xs text-slate-500">
          Last sync: {fmtDateTime(summary.updated)} · auto-refresh every 60s
        </p>
      )}

      {selected && (
        <StockDetailModal stock={selected} onClose={() => setSelected(null)} />
      )}
    </main>
  )
}
