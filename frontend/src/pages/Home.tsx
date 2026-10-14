import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
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
  // Which tab the detail modal opens on (row click -> chart, button -> fundamentals).
  const [detailTab, setDetailTab] = useState<'chart' | 'fundamentals'>('chart')
  const queryClient = useQueryClient()

  const openDetail = (stock: Stock, tab: 'chart' | 'fundamentals') => {
    setSelected(stock)
    setDetailTab(tab)
  }

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
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['watchlist'] }),
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
    <main className="w-full px-3 py-3">
      {/* Toolbar: index selector + market breadth + refresh */}
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted">Indices</span>
          <IndexMultiSelect
            options={indexOptions}
            selected={selectedIndexes}
            onChange={(next) => {
              setSelectedIndexes(next)
              setSelected(null)
            }}
          />
        </div>

        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-1">
            {marketUp ? (
              <TrendingUp size={14} className="text-bull" />
            ) : (
              <TrendingDown size={14} className="text-bear" />
            )}
            <span className={marketUp ? 'text-bull' : 'text-bear'}>
              {marketUp ? 'Bullish' : 'Bearish'}
            </span>
          </div>
          <div className="hidden items-center gap-2 sm:flex">
            <span className="text-bull">{summary.gainers} up</span>
            <span className="text-bear">{summary.losers} down</span>
            <span className="text-subtle">{summary.unchanged} flat</span>
          </div>
          <button
            onClick={() => refetch()}
            className="flex items-center gap-1 rounded-lg px-2 py-1 text-muted ring-1 ring-line transition hover:bg-panelalt hover:text-ink"
          >
            <RefreshCw size={13} className={isFetching ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      <div className="overflow-x-auto rounded-lg ring-1 ring-line">
        <table className="w-full whitespace-nowrap text-left text-xs">
          <thead className="bg-panelalt text-[10px] uppercase tracking-wide text-muted">
            <tr>
              <th className="px-3 py-2">Ticker</th>
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">Index</th>
              <th className="px-3 py-2 text-right">Last</th>
              <th className="px-3 py-2 text-right">Change</th>
              <th className="px-3 py-2 text-right">%</th>
              <th className="px-3 py-2 text-right">Volume</th>
              <th className="px-3 py-2 text-center">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {isLoading && (
              <tr>
                <td colSpan={8} className="px-3 py-8 text-center text-subtle">
                  Loading market data…
                </td>
              </tr>
            )}
            {!isLoading && stocks.length === 0 && (
              <tr>
                <td colSpan={8} className="px-3 py-8 text-center text-subtle">
                  No stocks match the selected indices.
                </td>
              </tr>
            )}
            {stocks.map((s) => {
              const up = (s.change ?? 0) >= 0
              const tone =
                s.change == null ? 'text-muted' : up ? 'text-bull' : 'text-bear'
              const watched = watchSet.has(s.ticker)
              return (
                <tr
                  key={s.id}
                  onClick={() => openDetail(s, 'chart')}
                  className="cursor-pointer bg-panel transition hover:bg-panelalt"
                >
                  <td className="px-3 py-1.5 font-semibold">
                    {s.ticker.replace('.JK', '')}
                  </td>
                  <td className="px-3 py-1.5 text-muted">{s.name}</td>
                  <td className="px-3 py-1.5">
                    <div className="flex flex-wrap gap-1">
                      {s.indices.map((idx) => (
                        <span
                          key={idx}
                          className="rounded bg-panelalt px-1.5 py-0.5 text-[10px] text-muted"
                        >
                          {idx}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-3 py-1.5 text-right font-medium">
                    {fmtPrice(s.last_price)}
                  </td>
                  <td className={`px-3 py-1.5 text-right ${tone}`}>{fmtChange(s.change)}</td>
                  <td className={`px-3 py-1.5 text-right font-medium ${tone}`}>
                    <span className="inline-flex items-center justify-end gap-1">
                      {s.change != null &&
                        (up ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />)}
                      {fmtPct(s.change_percent)}
                    </span>
                  </td>
                  <td className="px-3 py-1.5 text-right text-subtle">
                    {fmtVolume(s.volume)}
                  </td>
                  <td className="px-3 py-1.5 text-center">
                    <div className="flex items-center justify-center gap-1">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          openDetail(s, 'fundamentals')
                        }}
                        title="View fundamentals"
                        className="inline-flex items-center justify-center rounded-md p-1 text-muted ring-1 ring-line transition hover:bg-active hover:text-ink"
                      >
                        <BarChart3 size={13} />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          if (!watched) add.mutate(s.ticker)
                        }}
                        disabled={watched || add.isPending}
                        title={watched ? 'On watchlist' : 'Add to watchlist'}
                        className={`inline-flex items-center justify-center rounded-md p-1 transition ${
                          watched
                            ? 'cursor-default text-bull'
                            : 'text-muted ring-1 ring-line hover:bg-active hover:text-ink'
                        }`}
                      >
                        {watched ? <Check size={13} /> : <Plus size={13} />}
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {summary.updated && (
        <p className="mt-2 text-[11px] text-subtle">
          Last sync: {fmtDateTime(summary.updated)} · auto-refresh every 60s
        </p>
      )}

      {selected && (
        <StockDetailModal
          stock={selected}
          onClose={() => setSelected(null)}
          initialTab={detailTab}
        />
      )}
    </main>
  )
}
