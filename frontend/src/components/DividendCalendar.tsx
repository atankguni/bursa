import { CalendarDays } from 'lucide-react'
import { useDividendCalendar } from '../hooks'
import { fmtPrice } from '../lib/format'

const MASK = '••••••'

const fmtDay = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })

/** Expected dividends (projected from last year's ex-dates) for holdings + watchlist. */
export default function DividendCalendar({ hideValues }: { hideValues: boolean }) {
  const { data = [], isLoading } = useDividendCalendar()

  return (
    <section className="surface overflow-hidden" aria-labelledby="divcal-title">
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line px-4 py-2.5">
        <h3
          id="divcal-title"
          className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted"
        >
          <CalendarDays size={12} aria-hidden /> Expected dividends · next 6 months
        </h3>
        <span className="text-[10px] text-subtle">
          Projected from last year’s ex-dates: estimates, not announcements
        </span>
      </div>
      {isLoading ? (
        <div className="px-4 py-6 text-center text-xs text-subtle">Loading…</div>
      ) : data.length === 0 ? (
        <div className="px-4 py-6 text-center text-xs text-subtle">
          No dividends expected in the next 6 months for your holdings or watchlist.
        </div>
      ) : (
        <ul className="divide-y divide-line">
          {data.map((d) => (
            <li
              key={d.ticker + d.expected_ex_date}
              className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-2 text-xs"
            >
              <div className="flex min-w-0 items-center gap-2">
                <span className="w-24 shrink-0 tabular-nums text-muted">
                  ~{fmtDay(d.expected_ex_date)}
                </span>
                <span className="font-semibold">{d.ticker}</span>
                {d.in_portfolio && (
                  <span className="rounded-xs bg-accent/10 px-1 py-0.5 text-[9px] text-accent">
                    holding
                  </span>
                )}
                {!d.in_portfolio && d.in_watchlist && (
                  <span className="rounded-xs bg-panelalt px-1 py-0.5 text-[9px] text-muted">
                    watchlist
                  </span>
                )}
                <span
                  title={`Last year's ex-date: ${fmtDay(d.based_on)}`}
                  className="rounded-xs px-1 py-0.5 text-[9px] text-subtle ring-1 ring-line"
                >
                  {d.regular ? 'regular' : 'estimate'}
                </span>
              </div>
              <div className="text-right tabular-nums">
                <span className="text-ink">Rp {fmtPrice(d.amount_per_share)}/share</span>
                {d.expected_income != null && (
                  <span className="ml-2 text-muted">
                    ≈ Rp{' '}
                    {hideValues ? (
                      <span aria-label="hidden" className="select-none tracking-widest">
                        {MASK}
                      </span>
                    ) : (
                      fmtPrice(d.expected_income)
                    )}{' '}
                    for you
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
