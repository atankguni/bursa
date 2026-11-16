import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  ArrowDownRight,
  ArrowUpRight,
  Loader2,
  RefreshCw,
  SlidersHorizontal,
} from 'lucide-react'
import { cancelScreenerSync, startScreenerSync, type ScreenerRow } from '../api'
import { useMarketOverview, useScreener, useSyncStatus } from '../hooks'
import { useAuth } from '../lib/auth'
import { useSettings } from '../lib/settings'
import { fmtPct, fmtPercent, fmtPrice, fmtRatio } from '../lib/format'
import BoardBadge from '../components/BoardBadge'
import TickerName from '../components/TickerName'
import Pagination from '../components/Pagination'
import SignalBadge from '../components/SignalBadge'
import StockDetailModal from '../components/StockDetailModal'
import Term from '../components/Term'
import { SkeletonRows } from '../components/ui/Skeleton'
import { isBool, isString, oneOf, useStoredState } from '../lib/storedState'

const PAGE_SIZES = [50, 100, 200] // the API caps a page at 200

/** Why a PBV / RoE cell is blank (shown as a tooltip on the dash). */
function blankReason(r: ScreenerRow, metric: 'pbv' | 'roe'): string | undefined {
  if (r[metric] != null) return undefined
  if (!r.has_fundamentals) return 'No fundamentals yet (an admin can sync them)'
  if (metric === 'pbv' && r.price == null) return 'No price data (possibly suspended)'
  return 'Not meaningful: book value / equity is negative'
}
const inputCls = 'input input-sm'

const isPageSize = oneOf(...PAGE_SIZES)

export default function Screener() {
  const { settings } = useSettings()
  const qc = useQueryClient()
  const [minScore, setMinScore] = useStoredState('screener.minScore', '', isString)
  const [maxPbv, setMaxPbv] = useStoredState('screener.maxPbv', '', isString)
  const [minRoe, setMinRoe] = useStoredState('screener.minRoe', '', isString)
  const [sector, setSector] = useStoredState('screener.sector', '', isString)
  const [buyOnly, setBuyOnly] = useStoredState('screener.positiveOnly', false, isBool)
  const [selected, setSelected] = useState<ScreenerRow | null>(null)
  // 0-based page, for the filters it was chosen with: any filter change starts
  // again from the first page.
  const [paging, setPaging] = useState({ filterKey: '', page: 0 })
  const [pageSize, setPageSize] = useStoredState('screener.pageSize', 100, isPageSize)

  const filters = {
    minScore: minScore ? Number(minScore) : undefined,
    maxPbv: maxPbv ? Number(maxPbv) : undefined,
    minRoe: minRoe ? Number(minRoe) / 100 : undefined, // UI in %, API in fraction
    sector: sector || undefined,
    buyOnly,
  }
  const filterKey = JSON.stringify(filters)
  const page = paging.filterKey === filterKey ? paging.page : 0
  const setPage = (p: number) => setPaging({ filterKey, page: p })
  const { data, isLoading, isFetching } = useScreener(filters, page, pageSize)
  const rows = data?.items ?? []
  const total = data?.total ?? 0
  const pageCount = Math.ceil(total / pageSize)
  const from = total === 0 ? 0 : page * pageSize + 1
  const to = Math.min(total, (page + 1) * pageSize)

  const goTo = (p: number) => {
    setPage(p)
    window.scrollTo({ top: 0 }) // the pager sits below a long table
  }
  const { data: overview } = useMarketOverview()
  const sectors = (overview?.sectors ?? []).map((s) => s.sector)

  // Background "sync missing data" job (admins start it; everyone sees progress).
  const { isAdmin } = useAuth()
  const { data: sync } = useSyncStatus()
  const startSync = useMutation({
    mutationFn: (all: boolean) => startScreenerSync({ all }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['screener', 'sync'] }),
  })
  const stopSync = useMutation({
    mutationFn: cancelScreenerSync,
    onSuccess: (st) => qc.setQueryData(['screener', 'sync'], st),
  })

  // When a run finishes (running: true -> false), refresh dependent data.
  const wasRunning = useRef(false)
  useEffect(() => {
    if (sync?.running) {
      wasRunning.current = true
    } else if (wasRunning.current) {
      wasRunning.current = false
      void qc.invalidateQueries({ queryKey: ['screener'] })
      void qc.invalidateQueries({ queryKey: ['recommendation'] })
      void qc.invalidateQueries({ queryKey: ['stocks'] })
      void qc.invalidateQueries({ queryKey: ['market', 'overview'] })
    }
  }, [sync?.running, qc])

  // Universe-wide count from the backend (the table is filtered and capped).
  const missing = sync?.missing ?? 0

  return (
    <main className="page">
      <div className="mb-5 lg:mb-6">
        <h2 className="page-title">Screener</h2>
        <p className="page-sub">
          Every rated IDX stock, ranked by its score. Narrow it down with the filters.
        </p>
      </div>

      {/* Filters */}
      <div className="surface mb-3 flex flex-wrap items-end gap-3 p-3">
        <div className="flex items-center gap-1.5 self-center text-xs font-medium text-muted">
          <SlidersHorizontal size={13} /> Filters
        </div>
        <div className="w-24">
          <label className="field-label">Min score</label>
          <input
            type="number"
            value={minScore}
            onChange={(e) => setMinScore(e.target.value)}
            placeholder="0-100"
            className={inputCls}
          />
        </div>
        <div className="w-24">
          <label className="field-label">Max PBV</label>
          <input
            type="number"
            value={maxPbv}
            onChange={(e) => setMaxPbv(e.target.value)}
            className={inputCls}
          />
        </div>
        <div className="w-24">
          <label className="field-label">Min RoE %</label>
          <input
            type="number"
            value={minRoe}
            onChange={(e) => setMinRoe(e.target.value)}
            className={inputCls}
          />
        </div>
        <div className="w-40">
          <label className="field-label">Sector</label>
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
          className={`rounded-sm px-3 py-1.5 text-xs font-medium ring-1 transition ${
            buyOnly
              ? 'bg-accent/15 text-accent ring-accent/30'
              : 'text-muted ring-line-strong hover:bg-panelalt hover:text-ink'
          }`}
        >
          Positive signals only
        </button>

        <div className="ml-auto flex h-8 items-center gap-3 self-end">
          <span className="text-xs text-subtle">
            {missing > 0 && <>{missing} missing · </>}
            {isFetching ? 'Loading…' : `${total} matched`}
          </span>
          {sync?.running ? (
            <div className="flex items-center gap-2 text-xs">
              <span className="flex items-center gap-1.5 text-muted" aria-live="polite">
                <Loader2 size={13} className="animate-spin" />
                {sync.mode === 'all' ? 'Syncing all' : 'Syncing'} {sync.done}/{sync.total}
                {sync.note && <span className="text-subtle">· {sync.note}</span>}
              </span>
              {isAdmin && (
                <button
                  onClick={() => stopSync.mutate()}
                  disabled={stopSync.isPending}
                  className="rounded-sm px-2.5 py-1.5 font-medium text-bear ring-1 ring-bear/30 transition hover:bg-bear/10 disabled:opacity-50"
                >
                  Stop
                </button>
              )}
            </div>
          ) : isAdmin ? (
            <div className="flex items-center gap-1.5">
              {sync?.last_error && (
                <span
                  className="max-w-[16rem] truncate text-2xs text-bear"
                  title={sync.last_error}
                >
                  {sync.last_error}
                </span>
              )}
              <button
                onClick={() => startSync.mutate(false)}
                disabled={startSync.isPending}
                title="Fetch fundamentals for up to 40 stocks missing data"
                className="flex items-center gap-1.5 rounded-sm px-3 py-1.5 text-xs font-medium text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink disabled:opacity-50"
              >
                <RefreshCw
                  size={13}
                  className={startSync.isPending ? 'animate-spin' : ''}
                />
                Sync 40
              </button>
              <button
                onClick={() => startSync.mutate(true)}
                disabled={startSync.isPending || missing === 0}
                title="Work through every stock never synced, in batches of 40 with a pause between them. Runs in the background; you can leave this page or stop it."
                className="rounded-sm px-3 py-1.5 text-xs font-medium text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink disabled:opacity-50"
              >
                Sync all
              </button>
            </div>
          ) : null}
        </div>
      </div>

      <div className="surface overflow-hidden">
        <div className="table-scroll relative overflow-x-auto">
          <table className="w-full whitespace-nowrap text-left text-xs">
            <thead className="table-head">
              <tr>
                <th scope="col" className="px-4 py-2.5">
                  Ticker
                </th>
                <th scope="col" className="hidden px-4 py-2.5 md:table-cell">
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
                  <Term id="pbv">PBV</Term>
                </th>
                <th scope="col" className="px-4 py-2.5 text-right">
                  <Term id="roe">RoE</Term>
                </th>
                <th scope="col" className="px-4 py-2.5">
                  Signal
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {isLoading && (
                <tr>
                  <td colSpan={8}>
                    <SkeletonRows rows={8} />
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
                      <span className="inline-flex items-center gap-1.5">
                        {r.ticker}
                        <BoardBadge board={r.board} compact />
                      </span>
                      <TickerName name={r.name} />
                    </td>
                    <td className="hidden px-4 py-2 text-muted md:table-cell">
                      {r.name}
                    </td>
                    <td className="px-4 py-2 text-subtle">{r.sector ?? '—'}</td>
                    <td
                      className="px-4 py-2 text-right font-medium tabular-nums"
                      title={
                        r.price == null ? 'No price data (possibly suspended)' : undefined
                      }
                    >
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
                        {r.change_percent == null ? '—' : fmtPct(r.change_percent)}
                      </span>
                    </td>
                    <td
                      className="px-4 py-2 text-right tabular-nums text-muted"
                      title={blankReason(r, 'pbv')}
                    >
                      {fmtRatio(r.pbv)}
                    </td>
                    <td
                      className="px-4 py-2 text-right tabular-nums text-muted"
                      title={blankReason(r, 'roe')}
                    >
                      {fmtPercent(r.roe)}
                    </td>
                    <td className="px-4 py-2">
                      <SignalBadge
                        rec={
                          r.score != null && r.rating && r.strength
                            ? {
                                score: r.score,
                                rating: r.rating,
                                strength: r.strength,
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

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <label className="flex items-center gap-1.5 text-2xs text-subtle">
          Rows per page
          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value))
              goTo(0)
            }}
            className="input input-sm w-auto"
          >
            {PAGE_SIZES.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <Pagination page={page} pageCount={pageCount} onChange={goTo} />
        <span className="text-2xs tabular-nums text-subtle">
          {total > 0 && `${from}–${to} of ${total}`}
        </span>
      </div>

      {selected && (
        <StockDetailModal
          stock={{
            ticker: selected.ticker,
            name: selected.name,
            indices: selected.indices,
            last_price: selected.price,
            change_percent: selected.change_percent,
            board: selected.board,
          }}
          onClose={() => setSelected(null)}
        />
      )}
    </main>
  )
}
