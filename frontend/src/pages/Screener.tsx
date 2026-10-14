import { useState } from 'react'
import { ArrowDownRight, ArrowUpRight, SlidersHorizontal } from 'lucide-react'
import type { ScreenerRow } from '../api'
import { useMarketOverview, useScreener } from '../hooks'
import { useSettings } from '../lib/settings'
import { fmtPercent, fmtPrice, fmtRatio } from '../lib/format'
import SignalBadge from '../components/SignalBadge'
import StockDetailModal from '../components/StockDetailModal'

const inputCls =
  'w-full rounded bg-panelalt/70 px-2.5 py-1.5 text-xs text-ink ring-1 ring-line-strong outline-none focus:ring-bull'

export default function Screener() {
  const { settings } = useSettings()
  const [minScore, setMinScore] = useState('')
  const [maxPbv, setMaxPbv] = useState('')
  const [minRoe, setMinRoe] = useState('')
  const [sector, setSector] = useState('')
  const [buyOnly, setBuyOnly] = useState(false)
  const [selected, setSelected] = useState<ScreenerRow | null>(null)

  const filters = {
    minScore: minScore ? Number(minScore) : undefined,
    maxPbv: maxPbv ? Number(maxPbv) : undefined,
    minRoe: minRoe ? Number(minRoe) / 100 : undefined, // UI in %, API in fraction
    sector: sector || undefined,
    buyOnly,
  }
  const { data: rows = [], isLoading, isFetching } = useScreener(filters)
  const { data: overview } = useMarketOverview()
  const sectors = (overview?.sectors ?? []).map((s) => s.sector)

  return (
    <main className="w-full animate-fade-in px-4 py-4">
      {/* Filters */}
      <div className="surface mb-3 flex flex-wrap items-end gap-3 p-3">
        <div className="flex items-center gap-1.5 self-center text-xs font-medium text-muted">
          <SlidersHorizontal size={13} /> Filters
        </div>
        <div className="w-24">
          <label className="mb-1 block text-[10px] uppercase tracking-wide text-subtle">
            Min score
          </label>
          <input
            type="number"
            value={minScore}
            onChange={(e) => setMinScore(e.target.value)}
            placeholder="0-100"
            className={inputCls}
          />
        </div>
        <div className="w-24">
          <label className="mb-1 block text-[10px] uppercase tracking-wide text-subtle">
            Max PBV
          </label>
          <input
            type="number"
            value={maxPbv}
            onChange={(e) => setMaxPbv(e.target.value)}
            className={inputCls}
          />
        </div>
        <div className="w-24">
          <label className="mb-1 block text-[10px] uppercase tracking-wide text-subtle">
            Min RoE %
          </label>
          <input
            type="number"
            value={minRoe}
            onChange={(e) => setMinRoe(e.target.value)}
            className={inputCls}
          />
        </div>
        <div className="w-40">
          <label className="mb-1 block text-[10px] uppercase tracking-wide text-subtle">
            Sector
          </label>
          <select
            value={sector}
            onChange={(e) => setSector(e.target.value)}
            className={inputCls}
          >
            <option value="">All</option>
            {sectors.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <button
          onClick={() => setBuyOnly((v) => !v)}
          className={`rounded px-3 py-1.5 text-xs font-medium ring-1 transition ${
            buyOnly
              ? 'bg-bull/15 text-bull ring-bull/30'
              : 'text-muted ring-line-strong hover:bg-panelalt hover:text-ink'
          }`}
        >
          Buy signals only
        </button>
        <span className="ml-auto self-center text-xs text-subtle">
          {isFetching ? 'Loading…' : `${rows.length} matched`}
        </span>
      </div>

      <div className="surface overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full whitespace-nowrap text-left text-xs">
            <thead className="bg-panelalt/70 text-[10px] uppercase tracking-wider text-muted">
              <tr>
                <th scope="col" className="px-4 py-2.5">
                  Ticker
                </th>
                <th scope="col" className="px-4 py-2.5">
                  Name
                </th>
                <th scope="col" className="px-4 py-2.5">
                  Sector
                </th>
                <th scope="col" className="px-4 py-2.5 text-right">
                  Price
                </th>
                <th scope="col" className="px-4 py-2.5 text-right">
                  Chg %
                </th>
                <th scope="col" className="px-4 py-2.5 text-right">
                  PBV
                </th>
                <th scope="col" className="px-4 py-2.5 text-right">
                  RoE
                </th>
                <th scope="col" className="px-4 py-2.5">
                  Signal
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {isLoading && (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-subtle">
                    Loading…
                  </td>
                </tr>
              )}
              {!isLoading && rows.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-subtle">
                    No stocks match these filters.
                  </td>
                </tr>
              )}
              {rows.map((r) => {
                const tone = !settings.colorizeChanges
                  ? 'text-muted'
                  : r.change_percent == null
                    ? 'text-muted'
                    : r.change_percent >= 0
                      ? 'text-bull'
                      : 'text-bear'
                return (
                  <tr
                    key={r.ticker}
                    onClick={() => setSelected(r)}
                    className="cursor-pointer bg-panel transition-colors hover:bg-panelalt/60"
                  >
                    <td className="px-4 py-2 font-semibold">
                      {r.ticker.replace('.JK', '')}
                    </td>
                    <td className="px-4 py-2 text-muted">{r.name}</td>
                    <td className="px-4 py-2 text-subtle">{r.sector ?? '—'}</td>
                    <td className="px-4 py-2 text-right font-medium tabular-nums">
                      {fmtPrice(r.price)}
                    </td>
                    <td className={`px-4 py-2 text-right tabular-nums ${tone}`}>
                      <span className="inline-flex items-center justify-end gap-0.5">
                        {r.change_percent != null &&
                          (r.change_percent >= 0 ? (
                            <ArrowUpRight size={12} aria-hidden />
                          ) : (
                            <ArrowDownRight size={12} aria-hidden />
                          ))}
                        {r.change_percent == null
                          ? '—'
                          : `${r.change_percent > 0 ? '+' : ''}${r.change_percent.toFixed(2)}%`}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums text-muted">
                      {fmtRatio(r.pbv)}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums text-muted">
                      {fmtPercent(r.roe)}
                    </td>
                    <td className="px-4 py-2">
                      <SignalBadge
                        rec={
                          r.score != null && r.rating
                            ? {
                                score: r.score,
                                rating: r.rating,
                                strength: r.strength ?? '',
                              }
                            : null
                        }
                      />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {selected && (
        <StockDetailModal
          stock={{
            ticker: selected.ticker,
            name: selected.name,
            indices: selected.indices,
            last_price: selected.price,
            change_percent: selected.change_percent,
          }}
          onClose={() => setSelected(null)}
        />
      )}
    </main>
  )
}
