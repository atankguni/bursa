import { useState } from 'react'
import { useDividendIncome } from '../hooks'
import { compactAmount } from '../lib/chartTheme'
import { fmtMoney } from '../lib/format'

const MONTHS = [
  'Jan',
  'Feb',
  'Mar',
  'Apr',
  'May',
  'Jun',
  'Jul',
  'Aug',
  'Sep',
  'Oct',
  'Nov',
  'Dec',
]
const HIDDEN = '•••'

/** "2026-11" → "Nov 2026" (or "Nov"). */
function monthLabel(key: string, withYear = false) {
  const [y, m] = key.split('-')
  const name = MONTHS[Number(m) - 1] ?? key
  return withYear ? `${name} ${y}` : name
}

/** A round axis top just above `v` (1, 1.5, 2, … 8 × a power of ten). */
function niceMax(v: number) {
  if (v <= 0) return 1
  const p = 10 ** Math.floor(Math.log10(v))
  const step = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10].find((s) => s * p >= v) ?? 10
  return step * p
}

// Expected months: the same hue, lighter and hatched, so they differ by more than colour.
const EXPECTED_FILL =
  'repeating-linear-gradient(135deg, rgb(var(--c-accent) / 0.6) 0 2px, rgb(var(--c-accent) / 0.22) 2px 5px)'

/** Net dividend income per month: 12 received (solid), 6 expected (hatched). */
export default function DividendIncomeChart({ hideValues }: { hideValues: boolean }) {
  const { data, isLoading, isError } = useDividendIncome()
  const [hover, setHover] = useState<number | null>(null)
  const money = (v: number) => (hideValues ? HIDDEN : `Rp ${fmtMoney(v)}`)

  if (isLoading) return <div className="surface skeleton h-64" />
  if (isError || !data) return null
  const { months } = data
  if (months.every((m) => m.received === 0 && m.expected === 0)) return null

  const top = niceMax(Math.max(...months.map((m) => m.received + m.expected)))
  const current = months.findIndex((m) => m.month === data.current_month)
  const shown = hover != null ? months[hover] : undefined

  return (
    <section className="surface p-4 sm:p-5" aria-labelledby="divincome-title">
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div>
          <h3 id="divincome-title" className="section-title">
            Dividend income
          </h3>
          <p className="text-2xs text-subtle">
            Per month by ex-date, after {data.dividend_tax_pct}% tax
          </p>
        </div>
        <dl className="flex gap-6">
          <div>
            <dt className="eyebrow">Last 12 months</dt>
            <dd className="text-lg font-semibold tabular-nums">
              {money(data.received_12m)}
            </dd>
          </div>
          <div>
            <dt className="eyebrow">Expected, next 6</dt>
            <dd className="text-lg font-semibold tabular-nums text-muted">
              {money(data.expected_6m)}
            </dd>
          </div>
        </dl>
      </div>

      <div className="mt-4 flex items-center gap-4 text-2xs text-muted" aria-hidden>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-xs bg-accent" /> Received
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span
            className="h-2.5 w-2.5 rounded-xs"
            style={{ background: EXPECTED_FILL }}
          />
          Expected (from last year&apos;s dates)
        </span>
      </div>

      {/* The plot: recessive gridlines at the top and middle, bars from the baseline. */}
      <div className="relative mt-3" aria-hidden onMouseLeave={() => setHover(null)}>
        <div className="relative h-44">
          {[1, 0.5].map((f) => (
            <div
              key={f}
              className="absolute inset-x-0 border-t border-dashed border-line"
              style={{ bottom: `${f * 100}%` }}
            >
              {!hideValues && (
                <span className="absolute -top-2 right-0 bg-panel pl-1 text-2xs text-subtle tabular-nums">
                  {compactAmount(top * f)}
                </span>
              )}
            </div>
          ))}
          <div className="absolute inset-0 flex items-end gap-[2px] border-b border-line-strong pr-10">
            {months.map((m, i) => {
              const r = (m.received / top) * 100
              const e = (m.expected / top) * 100
              return (
                <div
                  key={m.month}
                  className="group relative flex h-full flex-1 flex-col justify-end"
                  onMouseEnter={() => setHover(i)}
                >
                  {/* A full-height hit area, wider than the bar itself. */}
                  <div
                    className={`absolute inset-0 rounded-xs transition-colors ${hover === i ? 'bg-panelalt' : ''}`}
                  />
                  <div className="relative mx-auto flex h-full w-full max-w-7 flex-col justify-end">
                    {e > 0 && (
                      <div
                        className="rounded-t-xs"
                        style={{
                          height: `${e}%`,
                          minHeight: 2,
                          background: EXPECTED_FILL,
                        }}
                      />
                    )}
                    {r > 0 && (
                      <div
                        className={`bg-accent ${e > 0 ? 'mt-[2px]' : 'rounded-t-xs'}`}
                        style={{ height: `${r}%`, minHeight: 2 }}
                      />
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
        <div className="flex gap-[2px] pr-10 pt-1.5">
          {months.map((m, i) => (
            <span
              key={m.month}
              className={`flex-1 text-center text-2xs tabular-nums ${
                i === current ? 'font-semibold text-ink' : 'text-subtle'
              } ${i % 3 === current % 3 ? '' : 'max-sm:invisible'}`}
            >
              {monthLabel(m.month)}
            </span>
          ))}
        </div>

        {shown && hover != null && (
          <div
            className="pointer-events-none absolute -top-2 z-10 w-44 -translate-x-1/2 -translate-y-full rounded-sm bg-panel px-3 py-2 text-2xs shadow-pop ring-1 ring-line"
            style={{
              left: `clamp(5.5rem, calc(${((hover + 0.5) / months.length) * 100}% - ${
                ((hover + 0.5) / months.length) * 2.5
              }rem), calc(100% - 5.5rem))`,
            }}
          >
            <div className="mb-1 font-semibold text-ink">
              {monthLabel(shown.month, true)}
            </div>
            {shown.received > 0 && (
              <div className="flex justify-between gap-3">
                <span className="text-muted">Received</span>
                <span className="tabular-nums text-ink">{money(shown.received)}</span>
              </div>
            )}
            {shown.expected > 0 && (
              <div className="flex justify-between gap-3">
                <span className="text-muted">Expected</span>
                <span className="tabular-nums text-ink">{money(shown.expected)}</span>
              </div>
            )}
            {shown.received === 0 && shown.expected === 0 && (
              <div className="text-muted">No dividends</div>
            )}
          </div>
        )}
      </div>

      {/* The same figures as a table, for screen readers. */}
      <table className="sr-only">
        <caption>Dividend income per month, after tax</caption>
        <thead>
          <tr>
            <th scope="col">Month</th>
            <th scope="col">Received</th>
            <th scope="col">Expected</th>
          </tr>
        </thead>
        <tbody>
          {months.map((m) => (
            <tr key={m.month}>
              <th scope="row">{monthLabel(m.month, true)}</th>
              <td>{m.received ? money(m.received) : '—'}</td>
              <td>{m.expected ? money(m.expected) : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
