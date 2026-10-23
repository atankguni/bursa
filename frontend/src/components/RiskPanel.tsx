import { AlertTriangle } from 'lucide-react'
import { usePortfolioRisk } from '../hooks'
import { useSettings } from '../lib/settings'

const pct = (v: number | null | undefined, digits = 1) =>
  v == null ? '—' : `${v > 0 ? '+' : ''}${v.toFixed(digits)}%`

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-md bg-panelalt/50 px-3 py-2.5 ring-1 ring-line">
      <div className="text-[10px] uppercase tracking-wider text-muted">{label}</div>
      <div className="mt-0.5 text-base font-semibold tabular-nums text-ink">{value}</div>
      {hint && <div className="mt-0.5 text-[10px] text-subtle">{hint}</div>}
    </div>
  )
}

/** Portfolio risk: diversification, beta vs IHSG, stress test, drawdown, sectors. */
export default function RiskPanel({ enabled }: { enabled: boolean }) {
  const { data: r, isLoading } = usePortfolioRisk(enabled)
  const { settings } = useSettings()
  if (!enabled) return null
  if (isLoading || !r) {
    return (
      <div className="surface px-4 py-6 text-center text-xs text-subtle">
        Analysing risk…
      </div>
    )
  }
  const tone = (v: number | null) =>
    !settings.colorizeChanges || v == null || v === 0
      ? 'text-muted'
      : v > 0
        ? 'text-bull'
        : 'text-bear'

  return (
    <section className="surface p-4" aria-labelledby="risk-title">
      <h3
        id="risk-title"
        className="mb-3 text-[10px] uppercase tracking-wider text-muted"
      >
        Risk
      </h3>

      {r.warnings.length > 0 && (
        <ul className="mb-3 space-y-1">
          {r.warnings.map((w) => (
            <li
              key={w}
              className="flex items-center gap-1.5 rounded-sm bg-amber-500/10 px-2.5 py-1.5 text-[11px] text-amber-700 ring-1 ring-amber-500/25 dark:text-amber-300"
            >
              <AlertTriangle size={12} aria-hidden /> {w}
            </li>
          ))}
        </ul>
      )}

      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        <Stat
          label="Diversification"
          value={r.effective_holdings != null ? `≈ ${r.effective_holdings} stocks` : '—'}
          hint={`Largest ${pct(r.top_weight, 0).replace('+', '')} · top 3 ${pct(r.top3_weight, 0).replace('+', '')}`}
        />
        <Stat
          label="Beta vs IHSG"
          value={r.beta != null ? r.beta.toFixed(2) : '—'}
          hint={
            r.beta != null
              ? `Moves ~${r.beta.toFixed(1)}× the market`
              : 'Needs ~2 months of prices'
          }
        />
        <Stat
          label={`If IHSG ${pct(r.stress_ihsg_pct, 0)}`}
          value={
            r.stress_portfolio_pct != null ? `≈ ${pct(r.stress_portfolio_pct)}` : '—'
          }
          hint="Estimated from beta"
        />
        <Stat
          label="Max drawdown"
          value={pct(r.max_drawdown_pct)}
          hint="Worst peak-to-trough (time-weighted)"
        />
      </div>

      {r.last_day_portfolio_pct != null && r.last_day_ihsg_pct != null && (
        <p className="mt-3 text-xs text-muted">
          Last trading day: you{' '}
          <span className={`font-semibold ${tone(r.last_day_portfolio_pct)}`}>
            {pct(r.last_day_portfolio_pct, 2)}
          </span>{' '}
          vs IHSG{' '}
          <span className={`font-semibold ${tone(r.last_day_ihsg_pct)}`}>
            {pct(r.last_day_ihsg_pct, 2)}
          </span>
        </p>
      )}

      {r.sectors.length > 0 && (
        <div className="mt-4">
          <div className="mb-1.5 text-[10px] uppercase tracking-wider text-muted">
            Sector exposure
          </div>
          <div className="space-y-1.5">
            {r.sectors.map((s) => (
              <div key={s.sector} className="flex items-center gap-3 text-xs">
                <span className="w-44 shrink-0 truncate text-muted" title={s.sector}>
                  {s.sector}
                </span>
                <div className="h-2 flex-1 overflow-hidden rounded-xs bg-panelalt">
                  <div
                    className={`h-full rounded-xs ${s.weight > 40 ? 'bg-amber-500' : 'bg-active'}`}
                    style={{ width: `${Math.max(s.weight, 2)}%` }}
                  />
                </div>
                <span className="w-12 text-right tabular-nums text-ink">
                  {s.weight.toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
          <p className="mt-2 text-[10px] text-subtle">
            Beta per stock:{' '}
            {r.holdings
              .map((h) => `${h.ticker} ${h.beta != null ? h.beta.toFixed(2) : '—'}`)
              .join(' · ')}
          </p>
        </div>
      )}
    </section>
  )
}
