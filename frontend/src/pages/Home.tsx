import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
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
import { DEFAULT_INDEXES, addToWatchlist, type Stock } from '../api'
import { useIndexes, useStocks, useWatchlist } from '../hooks'
import { useSettings } from '../lib/settings'
import { fmtChange, fmtDateTime, fmtPct, fmtPrice, fmtVolume } from '../lib/format'
import IndexMultiSelect from '../components/IndexMultiSelect'
import SignalBadge from '../components/SignalBadge'
import StockDetailModal from '../components/StockDetailModal'

type DetailTab = 'chart' | 'fundamentals' | 'recommendation'
type SignalSort = 'off' | 'desc' | 'asc'
const NEXT_SORT: Record<SignalSort, SignalSort> = { off: 'desc', desc: 'asc', asc: 'off' }

export default function Home() {
  const { settings } = useSettings()
  const [selectedIndexes, setSelectedIndexes] = useState<string[]>(
    settings.defaultIndexes,
  )
  const [selected, setSelected] = useState<Stock | null>(null)
  const [detailTab, setDetailTab] = useState<DetailTab>('chart')
  const [buyOnly, setBuyOnly] = useState(false)
  const [signalSort, setSignalSort] = useState<SignalSort>('off')
  const queryClient = useQueryClient()

  const hidden = settings.hiddenColumns.home
  const rec = (key: string) => !hidden.includes(key)

  useEffect(() => {
    setSelectedIndexes(settings.defaultIndexes)
  }, [settings.defaultIndexes])

  const openDetail = (stock: Stock, tab: DetailTab) => {
    setSelected(stock)
    setDetailTab(tab)
  }

  const { data: serverIndexes } = useIndexes()
  const indexOptions =
    serverIndexes && serverIndexes.length > 0 ? serverIndexes : DEFAULT_INDEXES

  const { data: stocks = [], isLoading, isFetching, refetch } = useStocks(selectedIndexes)

  const { data: watchlist = [] } = useWatchlist()
  const watchSet = useMemo(() => new Set(watchlist.map((w) => w.ticker)), [watchlist])

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

  const signals = useMemo(() => {
    let strongBuy = 0
    let buy = 0
    for (const s of stocks) {
      const r = s.recommendation?.rating
      if (r === 'Strong Buy') strongBuy++
      else if (r === 'Buy') buy++
    }
    return { strongBuy, buy }
  }, [stocks])

  const rows = useMemo(() => {
    let out = stocks
    if (buyOnly) {
      out = out.filter(
        (s) =>
          s.recommendation?.rating === 'Buy' || s.recommendation?.rating === 'Strong Buy',
      )
    }
    if (signalSort !== 'off') {
      out = [...out].sort((a, b) => {
        const sa = a.recommendation?.score ?? -1
        const sb = b.recommendation?.score ?? -1
        return signalSort === 'desc' ? sb - sa : sa - sb
      })
    }
    return out
  }, [stocks, buyOnly, signalSort])

  const marketUp = summary.gainers >= summary.losers
  const colCount = 9 - hidden.length

  return (
    <main className="w-full animate-fade-in px-4 py-4">
      {/* Toolbar */}
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted">Indices</span>
          <IndexMultiSelect
            options={indexOptions}
            selected={selectedIndexes}
            onChange={(next) => {
              setSelectedIndexes(next)
              setSelected(null)
            }}
          />
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="inline-flex items-center gap-1.5 rounded bg-panelalt/70 px-2.5 py-1 font-medium ring-1 ring-line">
            {marketUp ? (
              <TrendingUp size={13} className="text-bull" />
            ) : (
              <TrendingDown size={13} className="text-bear" />
            )}
            <span className={marketUp ? 'text-bull' : 'text-bear'}>
              {marketUp ? 'Bullish' : 'Bearish'}
            </span>
          </span>

          <span className="hidden items-center gap-2.5 rounded bg-panelalt/70 px-2.5 py-1 ring-1 ring-line sm:inline-flex">
            <span className="text-bull">{summary.gainers} up</span>
            <span className="text-bear">{summary.losers} down</span>
            <span className="text-subtle">{summary.unchanged} flat</span>
          </span>

          <span
            className="inline-flex items-center gap-2 rounded bg-panelalt/70 px-2.5 py-1 ring-1 ring-line"
            title="Signal ratings are relative to the tracked universe"
          >
            <span className="text-bull">{signals.strongBuy} Strong Buy</span>
            <span className="text-bull/80">{signals.buy} Buy</span>
          </span>

          <button
            onClick={() => setBuyOnly((v) => !v)}
            className={`rounded px-2.5 py-1 font-medium ring-1 transition ${
              buyOnly
                ? 'bg-bull/15 text-bull ring-bull/30'
                : 'text-muted ring-line hover:bg-panelalt hover:text-ink'
            }`}
          >
            Buy only
          </button>
          <button
            onClick={() => refetch()}
            className="inline-flex items-center gap-1.5 rounded px-2.5 py-1 font-medium text-muted ring-1 ring-line transition hover:bg-panelalt hover:text-ink"
          >
            <RefreshCw size={13} className={isFetching ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      <div className="surface overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full whitespace-nowrap text-left text-xs">
            <thead className="bg-panelalt/70 text-[10px] uppercase tracking-wider text-muted">
              <tr>
                <th className="px-4 py-2.5">Ticker</th>
                <th className="px-4 py-2.5">Name</th>
                {rec('index') && <th className="px-4 py-2.5">Index</th>}
                <th className="px-4 py-2.5 text-right">Last</th>
                {rec('change') && <th className="px-4 py-2.5 text-right">Change</th>}
                {rec('pct') && <th className="px-4 py-2.5 text-right">%</th>}
                {rec('signal') && (
                  <th className="px-4 py-2.5">
                    <button
                      onClick={() => setSignalSort((s) => NEXT_SORT[s])}
                      className="inline-flex items-center gap-1 uppercase hover:text-ink"
                      title="Sort by signal score"
                    >
                      Signal
                      <span className="text-[8px]">
                        {signalSort === 'desc' ? '▼' : signalSort === 'asc' ? '▲' : '↕'}
                      </span>
                    </button>
                  </th>
                )}
                {rec('volume') && <th className="px-4 py-2.5 text-right">Volume</th>}
                <th className="px-4 py-2.5 text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {isLoading && (
                <tr>
                  <td colSpan={colCount} className="px-4 py-10 text-center text-subtle">
                    Loading market data…
                  </td>
                </tr>
              )}
              {!isLoading && rows.length === 0 && (
                <tr>
                  <td colSpan={colCount} className="px-4 py-10 text-center text-subtle">
                    {buyOnly
                      ? 'No Buy signals in this view.'
                      : 'No stocks match the selected indices.'}
                  </td>
                </tr>
              )}
              {rows.map((s) => {
                const up = (s.change ?? 0) >= 0
                const tone = !settings.colorizeChanges
                  ? 'text-muted'
                  : s.change == null
                    ? 'text-muted'
                    : up
                      ? 'text-bull'
                      : 'text-bear'
                const watched = watchSet.has(s.ticker)
                return (
                  <tr
                    key={s.id}
                    onClick={() => openDetail(s, 'chart')}
                    className="cursor-pointer bg-panel transition-colors hover:bg-panelalt/60"
                  >
                    <td className="px-4 py-2 font-semibold tracking-tight">
                      {s.ticker.replace('.JK', '')}
                    </td>
                    <td className="px-4 py-2 text-muted">{s.name}</td>
                    {rec('index') && (
                      <td className="px-4 py-2">
                        <div className="flex flex-wrap gap-1">
                          {s.indices.map((idx) => (
                            <span
                              key={idx}
                              className="rounded-sm bg-panelalt px-1.5 py-0.5 text-[10px] font-medium text-muted"
                            >
                              {idx}
                            </span>
                          ))}
                        </div>
                      </td>
                    )}
                    <td className="px-4 py-2 text-right font-semibold tabular-nums">
                      {fmtPrice(s.last_price)}
                    </td>
                    {rec('change') && (
                      <td className={`px-4 py-2 text-right tabular-nums ${tone}`}>
                        {fmtChange(s.change)}
                      </td>
                    )}
                    {rec('pct') && (
                      <td className={`px-4 py-2 text-right font-medium ${tone}`}>
                        <span className="inline-flex items-center justify-end gap-0.5 tabular-nums">
                          {s.change != null &&
                            (up ? (
                              <ArrowUpRight size={12} />
                            ) : (
                              <ArrowDownRight size={12} />
                            ))}
                          {fmtPct(s.change_percent)}
                        </span>
                      </td>
                    )}
                    {rec('signal') && (
                      <td className="px-4 py-2">
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            openDetail(s, 'recommendation')
                          }}
                          className="rounded transition hover:opacity-80"
                          title="View signal breakdown"
                        >
                          <SignalBadge rec={s.recommendation} />
                        </button>
                      </td>
                    )}
                    {rec('volume') && (
                      <td className="px-4 py-2 text-right tabular-nums text-subtle">
                        {fmtVolume(s.volume)}
                      </td>
                    )}
                    <td className="px-4 py-2">
                      <div className="flex items-center justify-center gap-1">
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            openDetail(s, 'fundamentals')
                          }}
                          title="View fundamentals"
                          className="inline-flex items-center justify-center rounded p-1.5 text-muted transition hover:bg-active hover:text-ink"
                        >
                          <BarChart3 size={14} />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            if (!watched) add.mutate(s.ticker)
                          }}
                          disabled={watched || add.isPending}
                          title={watched ? 'On watchlist' : 'Add to watchlist'}
                          className={`inline-flex items-center justify-center rounded p-1.5 transition ${
                            watched
                              ? 'cursor-default text-bull'
                              : 'text-muted hover:bg-active hover:text-ink'
                          }`}
                        >
                          {watched ? <Check size={14} /> : <Plus size={14} />}
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {summary.updated && (
        <p className="mt-3 text-[11px] text-subtle">
          Last sync: {fmtDateTime(summary.updated)} · signals relative to the tracked
          universe
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
