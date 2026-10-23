import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { fetchDataHealth, type HealthStatus } from '../api'
import { fmtShortDateTime, fmtTimeAgo } from '../lib/format'

const STATUS: Record<HealthStatus, { label: string; dot: string; text: string }> = {
  ok: { label: 'OK', dot: 'bg-bull', text: 'text-bull' },
  warn: {
    label: 'Check',
    dot: 'bg-amber-500',
    text: 'text-amber-600 dark:text-amber-400',
  },
  error: { label: 'Problem', dot: 'bg-bear', text: 'text-bear' },
}

function Card({
  title,
  status,
  children,
}: {
  title: string
  status: HealthStatus
  children: ReactNode
}) {
  const s = STATUS[status]
  return (
    <section className="surface p-4">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-xs font-semibold">{title}</h3>
        {/* Status is spelled out, never colour alone. */}
        <span
          className={`inline-flex items-center gap-1.5 text-[11px] font-medium ${s.text}`}
        >
          <span className={`h-2 w-2 rounded-full ${s.dot}`} aria-hidden />
          {s.label}
        </span>
      </div>
      <div className="space-y-1 text-xs text-muted">{children}</div>
    </section>
  )
}

const Row = ({ k, v }: { k: string; v: ReactNode }) => (
  <div className="flex justify-between gap-3">
    <span>{k}</span>
    <span className="text-right tabular-nums text-ink">{v}</span>
  </div>
)

/** Can the app's data be trusted right now? Jobs, freshness, coverage, anomalies. */
export default function DataHealth() {
  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ['data-health'],
    queryFn: fetchDataHealth,
  })
  const s = data?.sections

  return (
    <main className="w-full animate-fade-in px-4 py-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold tracking-tight">Data health</h2>
          <p className="text-[11px] text-subtle">
            Background jobs, data freshness and suspicious values
            {data && ` · checked ${fmtTimeAgo(data.generated_at)}`}
          </p>
        </div>
        <button
          onClick={() => void refetch()}
          className="inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink"
        >
          <RefreshCw size={13} className={isFetching ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      {isLoading || !s ? (
        <div className="surface px-4 py-10 text-center text-subtle">Checking…</div>
      ) : (
        <div className="space-y-3">
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            <Card title="Prices" status={s.prices.status}>
              <Row
                k={`Up to date (${s.prices.trading_day})`}
                v={`${s.prices.current} / ${s.prices.stocks} · ${s.prices.coverage_pct}%`}
              />
              <Row k="No prices at all" v={s.prices.no_prices} />
              <Row
                k={`No bar in 7+ days`}
                v={
                  <span title={s.prices.stale_sample.join(', ')}>
                    {s.prices.stale}
                    {s.prices.stale > 0 && ' (suspended?)'}
                  </span>
                }
              />
              <Row k="Intraday stocks (last day)" v={s.prices.intraday_tickers} />
              <Row k="Last 1-min bar" v={fmtShortDateTime(s.prices.intraday_last)} />
            </Card>
            <Card title="Fundamentals" status={s.fundamentals.status}>
              <Row k="From statements" v={s.fundamentals.statements} />
              <Row k="From Yahoo summary" v={s.fundamentals.summary} />
              <Row k="Missing" v={s.fundamentals.missing} />
              <Row k="Never tried (Screener → Sync all)" v={s.fundamentals.never_tried} />
            </Card>
            <Card
              title="Indices & IDX listing"
              status={s.indices.status === 'ok' ? s.listing.status : s.indices.status}
            >
              <Row k="Index quotes" v={s.indices.count} />
              <Row k="Last index update" v={fmtTimeAgo(s.indices.newest_update)} />
              <Row k="IDX listing synced" v={fmtTimeAgo(s.listing.synced_at)} />
              <Row k="Special monitoring" v={s.listing.boards['Watchlist'] ?? 0} />
            </Card>
          </div>

          <Card title="Scheduled jobs" status={s.jobs.status}>
            <div className="overflow-x-auto">
              <table className="w-full whitespace-nowrap text-left">
                <thead className="text-[10px] uppercase tracking-wider text-subtle">
                  <tr>
                    <th scope="col" className="py-1 pr-4">
                      Job
                    </th>
                    <th scope="col" className="py-1 pr-4">
                      Last run
                    </th>
                    <th scope="col" className="py-1 pr-4">
                      Result
                    </th>
                    <th scope="col" className="py-1">
                      Next run
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {s.jobs.items.map((j) => (
                    <tr key={j.id}>
                      <td
                        className="max-w-[22rem] truncate py-1.5 pr-4 text-ink"
                        title={j.id}
                      >
                        {j.description}
                      </td>
                      <td className="py-1.5 pr-4">
                        {j.last_run ? fmtTimeAgo(j.last_run) : 'not since restart'}
                      </td>
                      <td className="py-1.5 pr-4">
                        {j.ok == null ? (
                          '—'
                        ) : j.ok ? (
                          <span className="text-bull">OK</span>
                        ) : (
                          <span className="text-bear" title={j.error ?? ''}>
                            Failed
                          </span>
                        )}
                      </td>
                      <td className="py-1.5">{fmtShortDateTime(j.next_run)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <div className="grid gap-3 md:grid-cols-2">
            <Card title="Data provider calls" status={s.providers.status}>
              {s.providers.items.map((p) => (
                <div key={p.name}>
                  <Row k={p.name} v={`${p.calls_today} today · ${p.errors} errors`} />
                  {p.last_error && (
                    <p className="truncate text-[10px] text-bear" title={p.last_error}>
                      Last error: {p.last_error}
                    </p>
                  )}
                </div>
              ))}
              {s.providers.items.length === 0 && <p>No calls since restart.</p>}
            </Card>
            <Card title="Suspicious values" status={s.suspicious.status}>
              <p className="text-[11px] text-subtle">
                Share counts that disagree with IDX distort PBV and market cap; extreme
                ratios are often real (tiny equity) but worth a look.
              </p>
              {[...s.suspicious.share_mismatches, ...s.suspicious.extreme_values]
                .slice(0, 20)
                .map((x) => (
                  <Row key={x.ticker + x.issue} k={x.ticker} v={x.issue} />
                ))}
              {s.suspicious.share_mismatches.length +
                s.suspicious.extreme_values.length ===
                0 && <p>Nothing suspicious.</p>}
            </Card>
          </div>
        </div>
      )}
    </main>
  )
}
