import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Search, Star } from 'lucide-react'
import { setTracked } from '../api'
import { useCatalog } from '../hooks'
import { useSettings } from '../lib/settings'
import { fmtPrice } from '../lib/format'
import Pagination from '../components/Pagination'

const PAGE_SIZES = [50, 100, 200] // the API caps a page at 200

export default function Browse() {
  const [q, setQ] = useState('')
  const [debounced, setDebounced] = useState('')
  const [page, setPage] = useState(0) // 0-based
  const [pageSize, setPageSize] = useState(100)
  const qc = useQueryClient()
  const { settings } = useSettings()

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
      qc.invalidateQueries({ queryKey: ['catalog'] })
      qc.invalidateQueries({ queryKey: ['indexes'] })
    },
  })

  return (
    <main className="w-full animate-fade-in px-4 py-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold tracking-tight">Browse IDX</h2>
          <p className="text-[11px] text-subtle">
            {isLoading
              ? 'Loading…'
              : `${from}–${to} of ${total}${isFetching ? ' · updating…' : ''} · track a stock for live prices`}
          </p>
        </div>
        <div className="flex items-center gap-1.5 rounded bg-panelalt/70 py-1.5 pl-2.5 pr-2 text-xs ring-1 ring-line-strong focus-within:ring-bull">
          <Search size={13} className="text-muted" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search ticker or name…"
            className="w-56 bg-transparent text-ink outline-none placeholder:text-subtle"
          />
        </div>
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
                  <td colSpan={6} className="px-4 py-10 text-center text-subtle">
                    Loading catalog…
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
                    className="bg-panel transition-colors hover:bg-panelalt/60"
                  >
                    <td className="px-4 py-2 font-semibold">
                      {r.ticker.replace('.JK', '')}
                    </td>
                    <td className="max-w-[22rem] truncate px-4 py-2 text-muted">
                      {r.name}
                    </td>
                    <td className="px-4 py-2">
                      <div className="flex flex-wrap gap-1">
                        {r.indices.map((idx) => (
                          <span
                            key={idx}
                            className="rounded-sm bg-panelalt px-1.5 py-0.5 text-[10px] text-muted"
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
                      {r.change_percent == null
                        ? '—'
                        : `${r.change_percent > 0 ? '+' : ''}${r.change_percent.toFixed(2)}%`}
                    </td>
                    <td className="px-4 py-2 text-center">
                      <button
                        onClick={() =>
                          toggle.mutate({ ticker: r.ticker, tracked: !r.tracked })
                        }
                        disabled={toggle.isPending}
                        title={
                          r.tracked
                            ? 'Tracked — click to untrack'
                            : 'Track for live prices'
                        }
                        aria-pressed={r.tracked}
                        className={`inline-flex items-center justify-center rounded p-2 transition ${
                          r.tracked
                            ? 'text-bull'
                            : 'text-muted ring-1 ring-line-strong hover:bg-active hover:text-ink'
                        }`}
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
        <label className="flex items-center gap-1.5 text-[11px] text-subtle">
          Rows per page
          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value))
              goTo(0)
            }}
            className="rounded bg-panelalt/70 px-1.5 py-1 text-xs text-ink ring-1 ring-line-strong"
          >
            {PAGE_SIZES.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <Pagination page={page} pageCount={pageCount} onChange={goTo} />
        <span className="text-[11px] tabular-nums text-subtle">
          {total > 0 && `${from}–${to} of ${total}`}
        </span>
      </div>

      <p className="mt-3 text-[11px] text-subtle">
        Catalog prices update daily; tracked stocks also get intraday updates.
      </p>
    </main>
  )
}
