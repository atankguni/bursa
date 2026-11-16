import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Search, Star } from 'lucide-react'
import { setTracked, type CatalogRow } from '../api'
import { useCatalog } from '../hooks'
import { useAuth } from '../lib/auth'
import { useSettings } from '../lib/settings'
import { fmtPct, fmtPrice } from '../lib/format'
import BoardBadge from '../components/BoardBadge'
import TickerName from '../components/TickerName'
import Pagination from '../components/Pagination'
import StockDetailModal from '../components/StockDetailModal'
import { SkeletonRows } from '../components/ui/Skeleton'
import { oneOf, useStoredState } from '../lib/storedState'

const PAGE_SIZES = [50, 100, 200] // the API caps a page at 200

const isPageSize = oneOf(...PAGE_SIZES)

export default function Browse() {
  const [q, setQ] = useState('')
  const [debounced, setDebounced] = useState('')
  const [page, setPage] = useState(0) // 0-based
  const [pageSize, setPageSize] = useStoredState('browse.pageSize', 100, isPageSize)
  const [selected, setSelected] = useState<CatalogRow | null>(null)
  const qc = useQueryClient()
  const { settings } = useSettings()
  const { isAdmin } = useAuth() // tracking changes the shared universe

  useEffect(() => {
    const t = setTimeout(() => {
      setDebounced(q.trim())
      setPage(0) // a new search starts from the first page
    }, 300)
    return () => clearTimeout(t)
  }, [q])

  const { data, isLoading, isFetching } = useCatalog(debounced, page, pageSize)
  const rows = data?.items ?? []
  const total = data?.total ?? 0
  const pageCount = Math.ceil(total / pageSize)
  const from = total === 0 ? 0 : page * pageSize + 1
  const to = Math.min(total, (page + 1) * pageSize)

  const goTo = (p: number) => {
    setPage(p)
    window.scrollTo({ top: 0 }) // the pager sits below a long table
  }

  const toggle = useMutation({
    mutationFn: ({ ticker, tracked }: { ticker: string; tracked: boolean }) =>
      setTracked(ticker, tracked),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['catalog'] })
      void qc.invalidateQueries({ queryKey: ['indexes'] })
    },
  })

  return (
    <main className="page">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3 lg:mb-6">
        <div>
          <h2 className="page-title">Browse IDX</h2>
          <p className="page-sub">
            {isLoading
              ? 'Loading…'
              : `${from}–${to} of ${total}${isFetching ? ' · updating…' : ''} · track a stock for live prices`}
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-full bg-panel py-1.5 pr-3 pl-3 text-xs ring-1 ring-line-strong transition-shadow focus-within:ring-2 focus-within:ring-accent">
          <Search size={13} className="text-muted" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search ticker or name…"
            className="w-56 bg-transparent text-ink outline-hidden placeholder:text-subtle"
          />
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
                  Index
                </th>
                <th scope="col" className="px-4 py-2.5 text-right">
                  Last
                </th>
                <th scope="col" className="px-4 py-2.5 text-right">
                  Chg %
                </th>
                <th scope="col" className="px-4 py-2.5 text-center">
                  Track
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {isLoading && (
                <tr>
                  <td colSpan={6}>
                    <SkeletonRows rows={8} />
                  </td>
                </tr>
              )}
              {!isLoading && rows.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-10 text-center text-subtle">
                    No matches.
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
                    onKeyDown={(e) => {
                      if (e.target !== e.currentTarget) return // keys on the Track button
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        setSelected(r)
                      }
                    }}
                    tabIndex={0}
                    className="cursor-pointer bg-panel transition-colors hover:bg-panelalt/60 focus-visible:bg-panelalt/60 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-accent"
                  >
                    <td className="px-4 py-2 font-semibold">
                      <span className="inline-flex items-center gap-1.5">
                        {r.ticker}
                        <BoardBadge board={r.board} compact />
                      </span>
                      <TickerName name={r.name} />
                    </td>
                    <td className="hidden max-w-[22rem] truncate px-4 py-2 text-muted md:table-cell">
                      {r.name}
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex flex-wrap gap-1">
                        {r.indices.map((idx) => (
                          <span
                            key={idx}
                            className="rounded-xs bg-panelalt px-1.5 py-0.5 text-2xs text-muted"
                          >
                            {idx}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      {fmtPrice(r.last_price)}
                    </td>
                    <td className={`px-4 py-2 text-right tabular-nums ${tone}`}>
                      {r.change_percent == null ? '—' : fmtPct(r.change_percent)}
                    </td>
                    <td className="px-4 py-2 text-center">
                      <button
                        onClick={(e) => {
                          e.stopPropagation() // don't also open the detail modal
                          toggle.mutate({ ticker: r.ticker, tracked: !r.tracked })
                        }}
                        disabled={toggle.isPending || !isAdmin}
                        title={
                          !isAdmin
                            ? r.tracked
                              ? 'Tracked: gets intraday prices'
                              : 'Not tracked (an admin can track it)'
                            : r.tracked
                              ? 'Tracked — click to untrack'
                              : 'Track for live prices'
                        }
                        aria-pressed={r.tracked}
                        className={`inline-flex items-center justify-center rounded-sm p-2 transition ${
                          r.tracked
                            ? 'text-bull'
                            : 'text-muted ring-1 ring-line-strong enabled:hover:bg-active enabled:hover:text-ink'
                        } disabled:cursor-default`}
                      >
                        <Star size={14} className={r.tracked ? 'fill-current' : ''} />
                      </button>
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

      <p className="mt-3 text-2xs text-subtle">
        Catalog prices update daily; tracked stocks also get intraday updates.
      </p>
      {selected && (
        <StockDetailModal stock={selected} onClose={() => setSelected(null)} />
      )}
    </main>
  )
}
