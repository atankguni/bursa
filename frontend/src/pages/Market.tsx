import { type Mover } from '../api'
import { useMarketOverview } from '../hooks'
import { useSettings } from '../lib/settings'
import { fmtPrice } from '../lib/format'
import IndicesPanel from '../components/IndicesPanel'

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
      <div className="border-b border-line px-4 py-2.5 text-[10px] uppercase tracking-wider text-muted">
        {title}
      </div>
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
              <div className="truncate text-[10px] text-subtle">{m.name}</div>
            </div>
            <div className="shrink-0 text-right">
              <div className="text-xs tabular-nums">{fmtPrice(m.price)}</div>
              <div className={`text-[11px] font-medium tabular-nums ${tone}`}>
                {m.change_percent == null
                  ? '—'
                  : `${m.change_percent > 0 ? '+' : ''}${m.change_percent.toFixed(2)}%`}
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
    <main className="w-full animate-fade-in px-4 py-4">
      <div className="mb-3">
        <h2 className="text-sm font-semibold tracking-tight">Market overview</h2>
        <p className="text-[11px] text-subtle">
          Indices, breadth, movers and sector performance
        </p>
      </div>

      <div className="mb-3">
        <IndicesPanel />
      </div>

      {isLoading ? (
        <div className="surface px-4 py-10 text-center text-subtle">Loading…</div>
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <div className="surface px-4 py-3">
              <div className="text-[10px] uppercase tracking-wider text-muted">
                Advancing
              </div>
              <div className="mt-1 text-lg font-semibold text-bull tabular-nums">
                {data?.up ?? 0}
              </div>
            </div>
            <div className="surface px-4 py-3">
              <div className="text-[10px] uppercase tracking-wider text-muted">
                Declining
              </div>
              <div className="mt-1 text-lg font-semibold text-bear tabular-nums">
                {data?.down ?? 0}
              </div>
            </div>
            <div className="surface px-4 py-3">
              <div className="text-[10px] uppercase tracking-wider text-muted">
                Unchanged
              </div>
              <div className="mt-1 text-lg font-semibold text-muted tabular-nums">
                {data?.flat ?? 0}
              </div>
            </div>
          </div>

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
            <div className="mb-3 text-[10px] uppercase tracking-wider text-muted">
              Sector performance
            </div>
            <div className="space-y-2">
              {(data?.sectors ?? []).map((s) => {
                const pct = s.avg_change_percent
                const width = (Math.abs(pct) / maxAbs) * 100
                return (
                  <div key={s.sector} className="flex items-center gap-3 text-xs">
                    <span className="w-40 shrink-0 truncate text-muted" title={s.sector}>
                      {s.sector}
                      <span className="ml-1 text-[10px] text-subtle">({s.count})</span>
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
                      {pct.toFixed(2)}%
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
