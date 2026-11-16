import { type Mover } from '../api'
import { useMarketOverview } from '../hooks'
import { useSettings } from '../lib/settings'
import { fmtNum, fmtPct, fmtPrice } from '../lib/format'
import IndicesPanel from '../components/IndicesPanel'
import { SkeletonCard } from '../components/ui/Skeleton'

function MoverList({
  title,
  movers,
  tone,
}: {
  title: string
  movers: Mover[]
  tone: string
}) {
  return (
    <div className="surface overflow-hidden">
      <div className="section-title border-b border-line px-4 py-3">{title}</div>
      <ul className="divide-y divide-line">
        {movers.length === 0 && (
          <li className="px-4 py-4 text-center text-xs text-subtle">No data</li>
        )}
        {movers.map((m) => (
          <li
            key={m.ticker}
            className="flex items-center justify-between gap-3 px-4 py-2"
          >
            <div className="min-w-0">
              <div className="text-xs font-semibold">{m.ticker}</div>
              <div className="truncate text-2xs text-subtle">{m.name}</div>
            </div>
            <div className="shrink-0 text-right">
              <div className="text-xs tabular-nums">{fmtPrice(m.price)}</div>
              <div className={`text-2xs font-medium tabular-nums ${tone}`}>
                {m.change_percent == null ? '—' : fmtPct(m.change_percent)}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default function Market() {
  const { data, isLoading } = useMarketOverview()
  const { settings } = useSettings()

  const tone = (v: number | null | undefined) =>
    !settings.colorizeChanges || v == null || v === 0
      ? 'text-muted'
      : v > 0
        ? 'text-bull'
        : 'text-bear'

  const maxAbs = Math.max(
    1,
    ...(data?.sectors ?? []).map((s) => Math.abs(s.avg_change_percent)),
  )

  return (
    <main className="page">
      <div className="mb-5 lg:mb-6">
        <h2 className="page-title">Market overview</h2>
        <p className="page-sub">Indices, breadth, movers and sector performance</p>
      </div>

      <div className="mb-4">
        <IndicesPanel />
      </div>

      {isLoading ? (
        <SkeletonCard />
      ) : (
        <div className="space-y-4">
          <BreadthCard up={data?.up ?? 0} down={data?.down ?? 0} flat={data?.flat ?? 0} />

          <div className="grid gap-3 sm:grid-cols-2">
            <MoverList
              title="Top gainers"
              movers={data?.top_gainers ?? []}
              tone="text-bull"
            />
            <MoverList
              title="Top losers"
              movers={data?.top_losers ?? []}
              tone="text-bear"
            />
          </div>

          <div className="surface p-4">
            <div className="section-title mb-3">Sector performance</div>
            <div className="space-y-2">
              {(data?.sectors ?? []).map((s) => {
                const pct = s.avg_change_percent
                const width = (Math.abs(pct) / maxAbs) * 100
                return (
                  <div key={s.sector} className="flex items-center gap-3 text-xs">
                    <span className="w-40 shrink-0 truncate text-muted" title={s.sector}>
                      {s.sector}
                      <span className="ml-1 text-2xs text-subtle">({s.count})</span>
                    </span>
                    <div className="flex h-2 flex-1 items-center">
                      <div
                        className={`h-2 rounded-xs ${pct >= 0 ? 'bg-bull' : 'bg-bear'}`}
                        style={{ width: `${Math.max(width, 2)}%` }}
                      />
                    </div>
                    <span
                      className={`w-16 text-right font-medium tabular-nums ${tone(pct)}`}
                    >
                      {pct > 0 ? '+' : ''}
                      {fmtNum(pct, 2)}%
                    </span>
                  </div>
                )
              })}
              {(data?.sectors ?? []).length === 0 && (
                <div className="py-4 text-center text-xs text-subtle">No sector data</div>
              )}
            </div>
          </div>
        </div>
      )}
    </main>
  )
}

/** Advancing / declining / unchanged across the whole exchange, as one bar. */
function BreadthCard({ up, down, flat }: { up: number; down: number; flat: number }) {
  const total = up + down + flat || 1
  const pct = (n: number) => `${fmtNum((n / total) * 100)}%`
  return (
    <div className="surface p-4 sm:p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="section-title">Market breadth</div>
        <div className="text-2xs text-subtle">{fmtNum(total)} stocks traded</div>
      </div>
      <div
        className="mt-3 flex h-2 overflow-hidden rounded-full bg-panelalt"
        role="img"
        aria-label={`${up} advancing, ${down} declining, ${flat} unchanged`}
      >
        <span className="bg-bull" style={{ width: pct(up) }} />
        <span className="bg-subtle/40" style={{ width: pct(flat) }} />
        <span className="bg-bear" style={{ width: pct(down) }} />
      </div>
      <div className="mt-3 grid grid-cols-3 gap-4">
        {(
          [
            ['Advancing', up, 'text-bull'],
            ['Unchanged', flat, 'text-muted'],
            ['Declining', down, 'text-bear'],
          ] as const
        ).map(([label, n, tone]) => (
          <div key={label}>
            <div className="eyebrow">{label}</div>
            <div className={`mt-0.5 text-lg font-semibold tabular-nums ${tone}`}>
              {n}
              <span className="ml-1.5 text-2xs font-normal text-subtle">{pct(n)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
