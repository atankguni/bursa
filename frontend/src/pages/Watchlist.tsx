import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Info, RefreshCw, Trash2 } from 'lucide-react'
import {
  fetchWatchlist,
  refreshWatchlist,
  removeFromWatchlist,
  type WatchlistItem,
} from '../api'
import {
  fmtCompact,
  fmtPct,
  fmtPercent,
  fmtPrice,
  fmtRatio,
} from '../lib/format'
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
    <main className="mx-auto max-w-6xl px-6 py-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Watchlist</h2>
          <p className="text-xs text-slate-400">
            Stocks you are tracking — fundamentals are yearly (IDR).
          </p>
        </div>
        <button
          onClick={() => refresh.mutate()}
          disabled={refresh.isPending || items.length === 0}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-slate-300 ring-1 ring-slate-700 transition hover:bg-panelalt hover:text-white disabled:opacity-50"
        >
          <RefreshCw size={14} className={refresh.isPending || isFetching ? 'animate-spin' : ''} />
          {refresh.isPending ? 'Refreshing…' : 'Refresh fundamentals'}
        </button>
      </div>

      {refresh.isSuccess && (
        <div className="mb-3 flex items-center gap-2 rounded-lg bg-bull/10 px-3 py-2 text-xs text-bull">
          <Info size={14} /> Updated {refresh.data.tickers} tickers ({refresh.data.rows} rows).
        </div>
      )}

      <div className="overflow-x-auto rounded-xl ring-1 ring-slate-800">
        <table className="w-full whitespace-nowrap text-left text-sm">
          <thead className="bg-panelalt text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-4 py-3">Ticker</th>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3 text-right">Price</th>
              <th className="px-4 py-3 text-right">Chg %</th>
              <th className="px-4 py-3 text-right">Shares</th>
              <th className="px-4 py-3 text-right">Market Cap</th>
              <th className="px-4 py-3 text-right">Revenue</th>
              <th className="px-4 py-3 text-right">Net Income</th>
              <th className="px-4 py-3 text-right">Assets</th>
              <th className="px-4 py-3 text-right">Liabilities</th>
              <th className="px-4 py-3 text-right">Equity</th>
              <th className="px-4 py-3 text-right text-white">PBV</th>
              <th className="px-4 py-3 text-right text-white">RoE</th>
              <th className="px-4 py-3 text-center" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {isLoading && (
              <tr>
                <td colSpan={14} className="px-4 py-10 text-center text-slate-500">
                  Loading watchlist…
                </td>
              </tr>
            )}
            {!isLoading && items.length === 0 && (
              <tr>
                <td colSpan={14} className="px-4 py-10 text-center text-slate-500">
                  Watchlist is empty — add stocks from the Home page.
                </td>
              </tr>
            )}
            {items.map((it) => {
              const f = it.fundamental
              const m = it.metrics
              const chgTone =
                it.change_percent == null
                  ? 'text-slate-400'
                  : it.change_percent >= 0
                    ? 'text-bull'
                    : 'text-bear'
              return (
                <tr
                  key={it.id}
                  onClick={() => setSelected(it)}
                  className="cursor-pointer bg-panel transition hover:bg-panelalt"
                >
                  <td className="px-4 py-3 font-semibold">{it.ticker.replace('.JK', '')}</td>
                  <td className="px-4 py-3 text-slate-300">{it.name}</td>
                  <td className="px-4 py-3 text-right font-medium">{fmtPrice(it.last_price)}</td>
                  <td className={`px-4 py-3 text-right ${chgTone}`}>{fmtPct(it.change_percent)}</td>
                  <td className="px-4 py-3 text-right text-slate-400">
                    {fmtCompact(f?.total_shares)}
                  </td>
                  <td className="px-4 py-3 text-right text-slate-300">
                    {fmtCompact(m.market_cap)}
                  </td>
                  <td className="px-4 py-3 text-right text-slate-400">
                    {fmtCompact(f?.revenue)}
                  </td>
                  <td className="px-4 py-3 text-right text-slate-400">
                    {fmtCompact(f?.net_income)}
                  </td>
                  <td className="px-4 py-3 text-right text-slate-400">
                    {fmtCompact(f?.total_assets)}
                  </td>
                  <td className="px-4 py-3 text-right text-slate-400">
                    {fmtCompact(f?.total_liabilities)}
                  </td>
                  <td className="px-4 py-3 text-right text-slate-400">
                    {fmtCompact(f?.equity)}
                  </td>
                  <td className="px-4 py-3 text-right font-medium text-slate-100">
                    {fmtRatio(m.pbv)}
                  </td>
                  <td className="px-4 py-3 text-right font-medium text-slate-100">
                    {fmtPercent(m.roe)}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        remove.mutate(it.ticker)
                      }}
                      disabled={remove.isPending}
                      title="Remove from watchlist"
                      className="inline-flex items-center justify-center rounded-lg p-1.5 text-slate-400 ring-1 ring-slate-700 transition hover:bg-bear/20 hover:text-bear"
                    >
                      <Trash2 size={15} />
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-xs text-slate-500">
        PBV = market cap ÷ book value. RoE = net income ÷ equity. Values update on
        the latest yearly statements; use Refresh to re-fetch.
      </p>

      {selected && (
        <StockDetailModal stock={selected} onClose={() => setSelected(null)} />
      )}
    </main>
  )
}
