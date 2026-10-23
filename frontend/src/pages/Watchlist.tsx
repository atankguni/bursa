import { useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowDownRight, ArrowUpRight, Info, RefreshCw, Trash2 } from 'lucide-react'
import { refreshWatchlist, removeFromWatchlist, type WatchlistItem } from '../api'
import { useWatchlist } from '../hooks'
import { useAuth } from '../lib/auth'
import { useSettings } from '../lib/settings'
import { fmtCompact, fmtPct, fmtPercent, fmtPrice, fmtRatio } from '../lib/format'
import BoardBadge from '../components/BoardBadge'
import StockDetailModal from '../components/StockDetailModal'
import SignalBadge from '../components/SignalBadge'
import SortHeader, { type SortState } from '../components/SortHeader'

// Value each sortable column sorts by (null = missing data, always listed last).
const SORT_VALUE = {
  ticker: (it: WatchlistItem) => it.ticker,
  name: (it: WatchlistItem) => it.name,
  signal: (it: WatchlistItem) => it.recommendation?.score ?? null,
  price: (it: WatchlistItem) => it.last_price,
  change: (it: WatchlistItem) => it.change_percent,
  shares: (it: WatchlistItem) => it.fundamental?.total_shares ?? null,
  marketCap: (it: WatchlistItem) => it.metrics.market_cap,
  revenue: (it: WatchlistItem) => it.fundamental?.revenue ?? null,
  netIncome: (it: WatchlistItem) => it.fundamental?.net_income ?? null,
  assets: (it: WatchlistItem) => it.fundamental?.total_assets ?? null,
  liabilities: (it: WatchlistItem) => it.fundamental?.total_liabilities ?? null,
  equity: (it: WatchlistItem) => it.fundamental?.equity ?? null,
  pbv: (it: WatchlistItem) => it.metrics.pbv,
  roe: (it: WatchlistItem) => it.metrics.roe,
} satisfies Record<string, (it: WatchlistItem) => string | number | null>

type SortKey = keyof typeof SORT_VALUE
const TEXT_KEYS: SortKey[] = ['ticker', 'name']
const DEFAULT_SORT: SortState<SortKey> = { key: 'ticker', dir: 'asc' }

function sortItems(items: WatchlistItem[], { key, dir }: SortState<SortKey>) {
  const value = SORT_VALUE[key]
  const sign = dir === 'asc' ? 1 : -1
  return [...items].sort((a, b) => {
    const va = value(a)
    const vb = value(b)
    if (va == null || vb == null) {
      if (va == null && vb == null) return a.ticker.localeCompare(b.ticker)
      return va == null ? 1 : -1 // missing values last in either direction
    }
    const cmp =
      typeof va === 'string' && typeof vb === 'string'
        ? va.localeCompare(vb, undefined, { sensitivity: 'base' })
        : Number(va) - Number(vb)
    return cmp * sign || a.ticker.localeCompare(b.ticker)
  })
}

export default function Watchlist() {
  const [selected, setSelected] = useState<WatchlistItem | null>(null)
  const queryClient = useQueryClient()
  const { settings } = useSettings()
  const { isAdmin } = useAuth() // on-demand refresh calls the data provider
  const show = (key: string) => !settings.hiddenColumns.watchlist.includes(key)

  const { data: items = [], isLoading, isFetching } = useWatchlist({ poll: true })

  const [sort, setSort] = useState<SortState<SortKey>>(DEFAULT_SORT)
  const sorted = useMemo(() => sortItems(items, sort), [items, sort])
  // Same column flips direction; a new column starts A→Z for text, high→low for numbers.
  const onSort = (key: SortKey) =>
    setSort((s) =>
      s.key === key
        ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' }
        : { key, dir: TEXT_KEYS.includes(key) ? 'asc' : 'desc' },
    )
  const sortProps = { sort, onSort }

  const remove = useMutation({
    mutationFn: (ticker: string) => removeFromWatchlist(ticker),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['watchlist'] }),
  })

  const refresh = useMutation({
    mutationFn: refreshWatchlist,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['watchlist'] }),
  })

  const colCount = 15 - settings.hiddenColumns.watchlist.length

  return (
    <main className="w-full animate-fade-in px-4 py-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-baseline gap-2">
          <h2 className="text-sm font-semibold tracking-tight">Watchlist</h2>
          <p className="text-[11px] text-subtle">
            Fundamentals are yearly (IDR) · PBV &amp; RoE vs latest price
          </p>
        </div>
        {isAdmin && (
          <button
            onClick={() => refresh.mutate()}
            disabled={refresh.isPending || items.length === 0}
            className="inline-flex items-center gap-1.5 rounded-sm px-2.5 py-1 text-xs font-medium text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink disabled:opacity-50"
          >
            <RefreshCw
              size={13}
              className={refresh.isPending || isFetching ? 'animate-spin' : ''}
            />
            {refresh.isPending ? 'Refreshing…' : 'Refresh fundamentals'}
          </button>
        )}
      </div>

      {refresh.isSuccess && (
        <div className="mb-3 flex items-center gap-1.5 rounded-sm bg-accent/10 px-3 py-2 text-[11px] text-accent ring-1 ring-accent/20">
          <Info size={13} /> Updated {refresh.data.tickers} tickers ({refresh.data.rows}{' '}
          rows).
        </div>
      )}

      <div className="surface overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full whitespace-nowrap text-left text-xs">
            <thead className="bg-panelalt/70 text-[10px] uppercase tracking-wider text-muted">
              <tr>
                <SortHeader sortKey="ticker" {...sortProps}>
                  Ticker
                </SortHeader>
                {show('name') && (
                  <SortHeader sortKey="name" {...sortProps}>
                    Name
                  </SortHeader>
                )}
                {show('signal') && (
                  <SortHeader sortKey="signal" {...sortProps}>
                    Signal
                  </SortHeader>
                )}
                <SortHeader sortKey="price" align="right" {...sortProps}>
                  Price
                </SortHeader>
                <SortHeader sortKey="change" align="right" {...sortProps}>
                  Chg %
                </SortHeader>
                {show('shares') && (
                  <SortHeader sortKey="shares" align="right" {...sortProps}>
                    Shares
                  </SortHeader>
                )}
                {show('marketCap') && (
                  <SortHeader sortKey="marketCap" align="right" {...sortProps}>
                    Market Cap
                  </SortHeader>
                )}
                {show('revenue') && (
                  <SortHeader sortKey="revenue" align="right" {...sortProps}>
                    Revenue
                  </SortHeader>
                )}
                {show('netIncome') && (
                  <SortHeader sortKey="netIncome" align="right" {...sortProps}>
                    Net Income
                  </SortHeader>
                )}
                {show('assets') && (
                  <SortHeader sortKey="assets" align="right" {...sortProps}>
                    Assets
                  </SortHeader>
                )}
                {show('liabilities') && (
                  <SortHeader sortKey="liabilities" align="right" {...sortProps}>
                    Liabilities
                  </SortHeader>
                )}
                {show('equity') && (
                  <SortHeader sortKey="equity" align="right" {...sortProps}>
                    Equity
                  </SortHeader>
                )}
                {show('pbv') && (
                  <SortHeader
                    sortKey="pbv"
                    align="right"
                    className="text-ink"
                    {...sortProps}
                  >
                    PBV
                  </SortHeader>
                )}
                {show('roe') && (
                  <SortHeader
                    sortKey="roe"
                    align="right"
                    className="text-ink"
                    {...sortProps}
                  >
                    RoE
                  </SortHeader>
                )}
                <th scope="col" className="px-4 py-2.5 text-center" />
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {isLoading && (
                <tr>
                  <td colSpan={colCount} className="px-4 py-10 text-center text-subtle">
                    Loading watchlist…
                  </td>
                </tr>
              )}
              {!isLoading && items.length === 0 && (
                <tr>
                  <td colSpan={colCount} className="px-4 py-10 text-center text-subtle">
                    Watchlist is empty — add stocks from the Home page.
                  </td>
                </tr>
              )}
              {sorted.map((it) => {
                const f = it.fundamental
                const m = it.metrics
                const chgTone = !settings.colorizeChanges
                  ? 'text-muted'
                  : it.change_percent == null
                    ? 'text-muted'
                    : it.change_percent >= 0
                      ? 'text-bull'
                      : 'text-bear'
                return (
                  <tr
                    key={it.ticker}
                    onClick={() => setSelected(it)}
                    className="cursor-pointer bg-panel transition-colors hover:bg-panelalt/60"
                  >
                    <td className="px-4 py-2 font-semibold tracking-tight">
                      <span className="inline-flex items-center gap-1.5">
                        {it.ticker}
                        <BoardBadge board={it.board} compact />
                        {f?.financial_currency && f.financial_currency !== 'IDR' && (
                          <span
                            title={`Reported in ${f.financial_currency}, converted to IDR`}
                            className="rounded-xs bg-panelalt px-1 py-0.5 text-[9px] font-normal text-muted"
                          >
                            {f.financial_currency}
                          </span>
                        )}
                      </span>
                    </td>
                    {show('name') && <td className="px-4 py-2 text-muted">{it.name}</td>}
                    {show('signal') && (
                      <td className="px-4 py-2">
                        <SignalBadge rec={it.recommendation} />
                      </td>
                    )}
                    <td className="px-4 py-2 text-right font-semibold">
                      {fmtPrice(it.last_price)}
                    </td>
                    <td className={`px-4 py-2 text-right font-medium ${chgTone}`}>
                      <span className="inline-flex items-center justify-end gap-0.5">
                        {it.change_percent != null &&
                          (it.change_percent >= 0 ? (
                            <ArrowUpRight size={12} aria-hidden />
                          ) : (
                            <ArrowDownRight size={12} aria-hidden />
                          ))}
                        {fmtPct(it.change_percent)}
                      </span>
                    </td>
                    {show('shares') && (
                      <td className="px-4 py-2 text-right text-subtle">
                        {fmtCompact(f?.total_shares)}
                      </td>
                    )}
                    {show('marketCap') && (
                      <td className="px-4 py-2 text-right text-muted">
                        {fmtCompact(m.market_cap)}
                      </td>
                    )}
                    {show('revenue') && (
                      <td className="px-4 py-2 text-right text-subtle">
                        {fmtCompact(f?.revenue)}
                      </td>
                    )}
                    {show('netIncome') && (
                      <td className="px-4 py-2 text-right text-subtle">
                        {fmtCompact(f?.net_income)}
                      </td>
                    )}
                    {show('assets') && (
                      <td className="px-4 py-2 text-right text-subtle">
                        {fmtCompact(f?.total_assets)}
                      </td>
                    )}
                    {show('liabilities') && (
                      <td className="px-4 py-2 text-right text-subtle">
                        {fmtCompact(f?.total_liabilities)}
                      </td>
                    )}
                    {show('equity') && (
                      <td className="px-4 py-2 text-right text-subtle">
                        {fmtCompact(f?.equity)}
                      </td>
                    )}
                    {show('pbv') && (
                      <td className="px-4 py-2 text-right font-semibold text-ink">
                        {fmtRatio(m.pbv)}
                      </td>
                    )}
                    {show('roe') && (
                      <td className="px-4 py-2 text-right font-semibold text-ink">
                        {fmtPercent(m.roe)}
                      </td>
                    )}
                    <td className="px-4 py-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          remove.mutate(it.ticker)
                        }}
                        disabled={remove.isPending}
                        title="Remove from watchlist"
                        className="mx-auto flex items-center justify-center rounded-sm p-2 text-muted transition hover:bg-bear/15 hover:text-bear"
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      <p className="mt-3 text-[11px] text-subtle">
        Figures are normalized to IDR (foreign-currency filers converted). PBV = market
        cap ÷ book value. RoE = net income ÷ equity.
      </p>

      {selected && (
        <StockDetailModal stock={selected} onClose={() => setSelected(null)} />
      )}
    </main>
  )
}
