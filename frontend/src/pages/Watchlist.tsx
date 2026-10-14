import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Info, RefreshCw, Trash2 } from 'lucide-react'
import {
  fetchWatchlist,
  refreshWatchlist,
  removeFromWatchlist,
  type WatchlistItem,
} from '../api'
import { fmtCompact, fmtPct, fmtPercent, fmtPrice, fmtRatio } from '../lib/format'
import StockDetailModal from '../components/StockDetailModal'

export default function Watchlist() {
  const [selected, setSelected] = useState<WatchlistItem | null>(null)
  const queryClient = useQueryClient()

  const { data: items = [], isLoading, isFetching } = useQuery({
    queryKey: ['watchlist'],
    queryFn: fetchWatchlist,
  })

  const remove = useMutation({
    mutationFn: (ticker: string) => removeFromWatchlist(ticker),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['watchlist'] }),
  })

  const refresh = useMutation({
    mutationFn: refreshWatchlist,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['watchlist'] }),
  })

  return (
    <main className="w-full px-3 py-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-baseline gap-2">
          <h2 className="text-sm font-semibold">Watchlist</h2>
          <p className="text-[11px] text-subtle">
            Fundamentals are yearly (IDR) · PBV &amp; RoE computed vs latest price
          </p>
        </div>
        <button
          onClick={() => refresh.mutate()}
          disabled={refresh.isPending || items.length === 0}
          className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs text-muted ring-1 ring-line transition hover:bg-panelalt hover:text-ink disabled:opacity-50"
        >
          <RefreshCw
            size={13}
            className={refresh.isPending || isFetching ? 'animate-spin' : ''}
          />
          {refresh.isPending ? 'Refreshing…' : 'Refresh fundamentals'}
        </button>
      </div>

      {refresh.isSuccess && (
        <div className="mb-2 flex items-center gap-1.5 rounded-lg bg-bull/10 px-2.5 py-1.5 text-[11px] text-bull">
          <Info size={13} /> Updated {refresh.data.tickers} tickers ({refresh.data.rows} rows).
        </div>
      )}

      <div className="overflow-x-auto rounded-lg ring-1 ring-line">
        <table className="w-full whitespace-nowrap text-left text-xs">
          <thead className="bg-panelalt text-[10px] uppercase tracking-wide text-muted">
            <tr>
              <th className="px-3 py-2">Ticker</th>
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2 text-right">Price</th>
              <th className="px-3 py-2 text-right">Chg %</th>
              <th className="px-3 py-2 text-right">Shares</th>
              <th className="px-3 py-2 text-right">Market Cap</th>
              <th className="px-3 py-2 text-right">Revenue</th>
              <th className="px-3 py-2 text-right">Net Income</th>
              <th className="px-3 py-2 text-right">Assets</th>
              <th className="px-3 py-2 text-right">Liabilities</th>
              <th className="px-3 py-2 text-right">Equity</th>
              <th className="px-3 py-2 text-right text-ink">PBV</th>
              <th className="px-3 py-2 text-right text-ink">RoE</th>
              <th className="px-3 py-2 text-center" />
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {isLoading && (
              <tr>
                <td colSpan={14} className="px-3 py-8 text-center text-subtle">
                  Loading watchlist…
                </td>
              </tr>
            )}
            {!isLoading && items.length === 0 && (
              <tr>
                <td colSpan={14} className="px-3 py-8 text-center text-subtle">
                  Watchlist is empty — add stocks from the Home page.
                </td>
              </tr>
            )}
            {items.map((it) => {
              const f = it.fundamental
              const m = it.metrics
              const chgTone =
                it.change_percent == null
                  ? 'text-muted'
                  : it.change_percent >= 0
                    ? 'text-bull'
                    : 'text-bear'
              return (
                <tr
                  key={it.id}
                  onClick={() => setSelected(it)}
                  className="cursor-pointer bg-panel transition hover:bg-panelalt"
                >
                  <td className="px-3 py-1.5 font-semibold">
                    <span className="inline-flex items-center gap-1.5">
                      {it.ticker.replace('.JK', '')}
                      {f?.financial_currency && f.financial_currency !== 'IDR' && (
                        <span
                          title={`Reported in ${f.financial_currency}, converted to IDR`}
                          className="rounded bg-panelalt px-1 py-0.5 text-[9px] font-normal text-muted"
                        >
                          {f.financial_currency}
                        </span>
                      )}
                    </span>
                  </td>
                  <td className="px-3 py-1.5 text-muted">{it.name}</td>
                  <td className="px-3 py-1.5 text-right font-medium">
                    {fmtPrice(it.last_price)}
                  </td>
                  <td className={`px-3 py-1.5 text-right ${chgTone}`}>
                    {fmtPct(it.change_percent)}
                  </td>
                  <td className="px-3 py-1.5 text-right text-subtle">
                    {fmtCompact(f?.total_shares)}
                  </td>
                  <td className="px-3 py-1.5 text-right text-muted">
                    {fmtCompact(m.market_cap)}
                  </td>
                  <td className="px-3 py-1.5 text-right text-subtle">
                    {fmtCompact(f?.revenue)}
                  </td>
                  <td className="px-3 py-1.5 text-right text-subtle">
                    {fmtCompact(f?.net_income)}
                  </td>
                  <td className="px-3 py-1.5 text-right text-subtle">
                    {fmtCompact(f?.total_assets)}
                  </td>
                  <td className="px-3 py-1.5 text-right text-subtle">
                    {fmtCompact(f?.total_liabilities)}
                  </td>
                  <td className="px-3 py-1.5 text-right text-subtle">
                    {fmtCompact(f?.equity)}
                  </td>
                  <td className="px-3 py-1.5 text-right font-medium text-ink">
                    {fmtRatio(m.pbv)}
                  </td>
                  <td className="px-3 py-1.5 text-right font-medium text-ink">
                    {fmtPercent(m.roe)}
                  </td>
                  <td className="px-3 py-1.5 text-center">
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        remove.mutate(it.ticker)
                      }}
                      disabled={remove.isPending}
                      title="Remove from watchlist"
                      className="inline-flex items-center justify-center rounded-md p-1 text-muted ring-1 ring-line transition hover:bg-bear/20 hover:text-bear"
                    >
                      <Trash2 size={13} />
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <p className="mt-2 text-[11px] text-subtle">
        Figures are normalized to IDR (foreign-currency filers converted). PBV =
        market cap ÷ book value. RoE = net income ÷ equity.
      </p>

      {selected && (
        <StockDetailModal stock={selected} onClose={() => setSelected(null)} />
      )}
    </main>
  )
}
