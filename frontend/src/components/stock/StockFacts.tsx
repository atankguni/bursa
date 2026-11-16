/** The stock pop-up's key facts: the latest day's open/high/low/volume and the 52-week range. */
import { useHistory } from '../../hooks'
import { fmtPrice, fmtVolume, parseServerTime } from '../../lib/format'

const YEAR_S = 365 * 24 * 3600
const dayFmt = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  timeZone: 'UTC', // daily bars sit at midnight UTC of their trading date
})
const jakartaDay = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Jakarta' })

export default function StockFacts({
  ticker,
  price,
}: {
  ticker: string
  /** The live price, placed on the 52-week range (else the latest close). */
  price: number | null
}) {
  // The same 1-year request the chart makes for its shorter spans (shared cache).
  const { data, isLoading } = useHistory(ticker, '1d', '1y')
  if (isLoading) return <div className="skeleton mt-3 h-10 max-w-xl" />
  const points = data?.points ?? []
  const day = points[points.length - 1]
  if (!day) return null

  const dayTime = parseServerTime(day.timestamp)?.getTime() ?? 0
  const from = dayTime / 1000 - YEAR_S
  const year = points.filter(
    (p) => (parseServerTime(p.timestamp)?.getTime() ?? 0) / 1000 >= from,
  )
  const lo = Math.min(...year.map((p) => p.low))
  const hi = Math.max(...year.map((p) => p.high))
  const now = price ?? day.close
  const at = hi > lo ? Math.min(Math.max((now - lo) / (hi - lo), 0), 1) : 0.5
  const isToday =
    dayTime > 0 &&
    new Date(dayTime).toISOString().slice(0, 10) === jakartaDay.format(new Date())

  const facts: [string, string][] = [
    ['Open', fmtPrice(day.open)],
    ['High', fmtPrice(day.high)],
    ['Low', fmtPrice(day.low)],
    ['Volume', fmtVolume(day.volume)],
  ]

  return (
    <div className="mt-3 flex flex-wrap items-end gap-x-6 gap-y-2">
      <dl className="grid w-full grid-cols-4 gap-x-3 sm:w-auto sm:gap-x-5">
        {facts.map(([k, v]) => (
          <div key={k}>
            <dt className="text-2xs text-subtle">{k}</dt>
            <dd className="text-xs font-medium tabular-nums text-ink">{v}</dd>
          </div>
        ))}
      </dl>
      <div className="w-full max-w-64 sm:w-56">
        <div className="flex justify-between text-2xs text-subtle">
          <span>52-week range</span>
          <span className="sr-only">
            {`: low ${fmtPrice(lo)}, high ${fmtPrice(hi)}, now ${Math.round(at * 100)}% of the way up`}
          </span>
        </div>
        <div className="relative mt-1 h-1.5 rounded-full bg-panelalt" aria-hidden>
          <div
            className="absolute inset-y-0 left-0 rounded-full bg-accent/30"
            style={{ width: `${at * 100}%` }}
          />
          <div
            className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-accent ring-2 ring-panel"
            style={{ left: `${at * 100}%` }}
          />
        </div>
        <div
          className="mt-1 flex justify-between text-2xs tabular-nums text-muted"
          aria-hidden
        >
          <span>{fmtPrice(lo)}</span>
          <span>{fmtPrice(hi)}</span>
        </div>
      </div>
      {!isToday && (
        <p className="w-full text-2xs text-subtle">
          Day figures are from {dayFmt.format(new Date(dayTime))}, the latest trading day.
        </p>
      )}
    </div>
  )
}
