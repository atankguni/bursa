import { lazy, Suspense, useState, type ReactNode } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Eye, EyeOff, Plus, Trash2 } from 'lucide-react'
import { deleteTransaction } from '../api'
import { usePortfolio, usePortfolioHistory, useStatus, useTransactions } from '../hooks'
import { useSettings } from '../lib/settings'
import { fmtPrice } from '../lib/format'
import BoardBadge from '../components/BoardBadge'
import DividendCalendar from '../components/DividendCalendar'
import RiskPanel from '../components/RiskPanel'
import TransactionModal from '../components/TransactionModal'

const PortfolioChart = lazy(() => import('../components/PortfolioChart'))

const signed = (v: number | null) =>
  v == null ? '—' : `${v > 0 ? '+' : ''}${fmtPrice(v)}`
const signedPct = (v: number | null) =>
  v == null ? '—' : `${v > 0 ? '+' : ''}${v.toFixed(2)}%`

// IDX lots: shares / lotSize (integer when whole).
const lotsOf = (shares: number, lotSize: number) => {
  const v = shares / lotSize
  return Number.isInteger(v) ? String(v) : v.toFixed(2)
}

/**
 * Privacy mask: when hidden, the real value is not rendered at all (not just
 * blurred), so it can't leak via screen share, zoom, selection or copy/paste.
 */
const MASK = '••••••'
function Secret({ hidden, children }: { hidden: boolean; children: ReactNode }) {
  return hidden ? (
    <span aria-label="hidden" className="select-none tracking-widest">
      {MASK}
    </span>
  ) : (
    <>{children}</>
  )
}

function Card({
  label,
  value,
  tone,
  hint,
  title,
}: {
  label: string
  value: ReactNode
  tone?: string
  hint?: ReactNode
  title?: string
}) {
  return (
    <div className="surface px-4 py-3" title={title}>
      <div className="text-[10px] uppercase tracking-wider text-muted">{label}</div>
      <div className={`mt-1 text-lg font-semibold tabular-nums ${tone ?? 'text-ink'}`}>
        {value}
      </div>
      {hint && <div className="mt-0.5 text-[10px] text-subtle">{hint}</div>}
    </div>
  )
}

export default function Portfolio() {
  const [adding, setAdding] = useState(false)
  const qc = useQueryClient()
  const { settings, update } = useSettings()
  const hide = settings.hidePortfolioValues
  const { data: pf, isLoading } = usePortfolio()
  const { data: txs = [] } = useTransactions()
  const { data: history = [] } = usePortfolioHistory()
  const { data: status } = useStatus()
  const lotSize = status?.lot_size ?? 100

  const remove = useMutation({
    mutationFn: deleteTransaction,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['portfolio'] }),
  })

  const tone = (v: number | null | undefined) => {
    if (!settings.colorizeChanges || v == null || v === 0) return 'text-muted'
    return v > 0 ? 'text-bull' : 'text-bear'
  }

  const [chartMode, setChartMode] = useState<'value' | 'return'>('value')
  // Latest time-weighted return vs IHSG over the same period.
  const lastPoint = [...history]
    .reverse()
    .flatMap((p) =>
      p.return_pct != null && p.benchmark_pct != null
        ? [{ mine: p.return_pct, ihsg: p.benchmark_pct }]
        : [],
    )[0]
  const firstPoint = history[0]
  const versus = lastPoint && firstPoint ? { since: firstPoint.date, ...lastPoint } : null

  const totals = pf?.totals
  const holdings = pf?.holdings ?? []

  return (
    <main className="w-full animate-fade-in px-4 py-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold tracking-tight">Portfolio</h2>
          <p className="text-[11px] text-subtle">
            Average-cost P/L · {holdings.length} position
            {holdings.length === 1 ? '' : 's'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => update({ hidePortfolioValues: !hide })}
            aria-pressed={hide}
            title={hide ? 'Show amounts' : 'Hide amounts (for screen sharing)'}
            className={`inline-flex items-center gap-1.5 rounded px-2.5 py-1.5 text-xs font-medium ring-1 transition ${
              hide
                ? 'bg-panelalt text-ink ring-line-strong'
                : 'text-muted ring-line-strong hover:bg-panelalt hover:text-ink'
            }`}
          >
            {hide ? <EyeOff size={14} /> : <Eye size={14} />}
            {hide ? 'Show values' : 'Hide values'}
          </button>
          <button
            onClick={() => setAdding(true)}
            className="inline-flex items-center gap-1.5 rounded bg-accent px-3 py-1.5 text-xs font-medium text-accent-ink transition hover:opacity-90"
          >
            <Plus size={14} /> Add transaction
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="surface px-4 py-10 text-center text-subtle">Loading…</div>
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Card
              label="Market value"
              value={<Secret hidden={hide}>{fmtPrice(totals?.market_value ?? 0)}</Secret>}
            />
            <Card
              label="Unrealized P/L"
              value={
                <>
                  <Secret hidden={hide}>{signed(totals?.unrealized_pl ?? 0)}</Secret> (
                  {signedPct(totals?.unrealized_pl_pct ?? null)})
                </>
              }
              tone={tone(totals?.unrealized_pl)}
              hint={
                <>
                  After selling costs:{' '}
                  <Secret hidden={hide}>
                    {signed((totals?.unrealized_pl ?? 0) - (totals?.exit_costs ?? 0))}
                  </Secret>
                </>
              }
              title="Selling everything now would cost about this much in broker fee + tax (Settings → Trading costs)"
            />
            <Card
              label="Day change"
              value={
                <>
                  <Secret hidden={hide}>{signed(totals?.day_change ?? 0)}</Secret> (
                  {signedPct(totals?.day_change_pct ?? null)})
                </>
              }
              tone={tone(totals?.day_change)}
            />
            <Card
              label="Invested"
              value={<Secret hidden={hide}>{fmtPrice(totals?.invested ?? 0)}</Secret>}
            />
            <Card
              label="Realized P/L"
              value={<Secret hidden={hide}>{signed(totals?.realized_pl ?? 0)}</Secret>}
              tone={tone(totals?.realized_pl)}
            />
            <Card
              label="Dividends received"
              value={
                <Secret hidden={hide}>{fmtPrice(totals?.dividends_received ?? 0)}</Secret>
              }
              hint="After tax, on shares held before each ex-date"
            />
            <Card
              label="Total return"
              value={<Secret hidden={hide}>{signed(totals?.total_return ?? 0)}</Secret>}
              tone={tone(totals?.total_return)}
              hint="P/L after selling costs + realized + dividends"
            />
            <Card
              label="Est. annual income"
              value={
                <Secret hidden={hide}>{fmtPrice(totals?.projected_income ?? 0)}</Secret>
              }
              hint="Last 12 months' dividends, after tax"
            />
          </div>

          {/* Holdings */}
          <div className="surface overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full whitespace-nowrap text-left text-xs">
                <thead className="bg-panelalt/70 text-[10px] uppercase tracking-wider text-muted">
                  <tr>
                    <th scope="col" className="px-4 py-2.5">
                      Ticker
                    </th>
                    <th scope="col" className="px-4 py-2.5 text-right">
                      Lots
                    </th>
                    <th scope="col" className="px-4 py-2.5 text-right">
                      Shares
                    </th>
                    <th scope="col" className="px-4 py-2.5 text-right">
                      Avg
                    </th>
                    <th scope="col" className="px-4 py-2.5 text-right">
                      Price
                    </th>
                    <th scope="col" className="px-4 py-2.5 text-right">
                      Value
                    </th>
                    <th scope="col" className="px-4 py-2.5 text-right">
                      P/L
                    </th>
                    <th scope="col" className="px-4 py-2.5 text-right">
                      P/L %
                    </th>
                    <th scope="col" className="px-4 py-2.5 text-right">
                      Day %
                    </th>
                    <th scope="col" className="px-4 py-2.5 text-right">
                      Weight
                    </th>
                    <th scope="col" className="px-4 py-2.5 text-right">
                      Est. income
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {holdings.length === 0 && (
                    <tr>
                      <td colSpan={11} className="px-4 py-10 text-center text-subtle">
                        No positions yet — add a transaction to get started.
                      </td>
                    </tr>
                  )}
                  {holdings.map((h) => (
                    <tr
                      key={h.ticker}
                      className="bg-panel transition-colors hover:bg-panelalt/60"
                    >
                      <td className="px-4 py-2 font-semibold">
                        <span className="inline-flex items-center gap-1.5">
                          {h.ticker.replace('.JK', '')}
                          <BoardBadge board={h.board} compact />
                          {h.split_adjusted && (
                            <span
                              title="Adjusted for a stock split: shares × ratio and price ÷ ratio, so invested capital is unchanged."
                              className="rounded-sm bg-panelalt px-1 py-0.5 text-[9px] font-normal text-muted"
                            >
                              split-adj.
                            </span>
                          )}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-right font-medium tabular-nums">
                        <Secret hidden={hide}>{lotsOf(h.quantity, lotSize)}</Secret>
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums text-muted">
                        <Secret hidden={hide}>
                          {h.quantity.toLocaleString('en-US')}
                        </Secret>
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums text-muted">
                        <Secret hidden={hide}>{fmtPrice(h.avg_cost)}</Secret>
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {fmtPrice(h.price)}
                      </td>
                      <td className="px-4 py-2 text-right font-medium tabular-nums">
                        <Secret hidden={hide}>{fmtPrice(h.market_value)}</Secret>
                      </td>
                      <td
                        className={`px-4 py-2 text-right tabular-nums ${tone(h.unrealized_pl)}`}
                      >
                        <Secret hidden={hide}>{signed(h.unrealized_pl)}</Secret>
                      </td>
                      <td
                        className={`px-4 py-2 text-right tabular-nums ${tone(h.unrealized_pl)}`}
                      >
                        {signedPct(h.unrealized_pl_pct)}
                      </td>
                      <td
                        className={`px-4 py-2 text-right tabular-nums ${tone(h.day_change)}`}
                      >
                        {signedPct(h.day_change_pct)}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums text-muted">
                        {h.weight != null ? `${h.weight.toFixed(1)}%` : '—'}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums text-muted">
                        <Secret hidden={hide}>
                          {h.projected_income ? fmtPrice(h.projected_income) : '—'}
                        </Secret>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <RiskPanel enabled={holdings.length > 0} />
          <DividendCalendar hideValues={hide} />

          {/* Equity curve */}
          {history.length > 1 && (
            <div className="surface p-4">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <div className="text-[10px] uppercase tracking-wider text-muted">
                  {chartMode === 'value' ? 'Portfolio value' : 'Your return vs IHSG'}
                </div>
                <div className="flex overflow-hidden rounded ring-1 ring-line-strong">
                  {(['value', 'return'] as const).map((m) => (
                    <button
                      key={m}
                      onClick={() => setChartMode(m)}
                      aria-pressed={chartMode === m}
                      className={`px-2.5 py-1 text-xs transition ${
                        chartMode === m
                          ? 'bg-active text-ink'
                          : 'text-muted hover:text-ink'
                      }`}
                    >
                      {m === 'value' ? 'Value' : 'Return vs IHSG'}
                    </button>
                  ))}
                </div>
              </div>
              {versus && (
                <p className="mb-2 text-xs text-muted">
                  Since {versus.since}: you{' '}
                  <span className={`font-semibold ${tone(versus.mine)}`}>
                    {signedPct(versus.mine)}
                  </span>{' '}
                  vs IHSG{' '}
                  <span className={`font-semibold ${tone(versus.ihsg)}`}>
                    {signedPct(versus.ihsg)}
                  </span>{' '}
                  → {versus.mine >= versus.ihsg ? 'ahead of' : 'behind'} the market by{' '}
                  <span className="font-semibold text-ink">
                    {Math.abs(versus.mine - versus.ihsg).toFixed(2)} pts
                  </span>
                  <span className="text-subtle">
                    {' '}
                    · time-weighted, dividends included (buys/sells don’t count as gains;
                    IHSG is price only)
                  </span>
                </p>
              )}
              <Suspense
                fallback={<div className="h-[260px] animate-pulse rounded bg-panelalt" />}
              >
                <PortfolioChart data={history} hideValues={hide} mode={chartMode} />
              </Suspense>
            </div>
          )}

          {/* Transactions */}
          {txs.length > 0 && (
            <div className="surface overflow-hidden">
              <div className="border-b border-line px-4 py-2.5 text-[10px] uppercase tracking-wider text-muted">
                Transactions
              </div>
              <div className="overflow-x-auto">
                <table className="w-full whitespace-nowrap text-left text-xs">
                  <tbody className="divide-y divide-line">
                    {txs.map((t) => (
                      <tr key={t.id} className="bg-panel">
                        <td className="px-4 py-2 text-muted">{t.trade_date}</td>
                        <td className="px-4 py-2 font-medium">
                          {t.ticker.replace('.JK', '')}
                        </td>
                        <td
                          className={`px-4 py-2 font-medium uppercase ${
                            t.side === 'buy' ? 'text-bull' : 'text-bear'
                          }`}
                        >
                          {t.side}
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums">
                          <Secret hidden={hide}>{lotsOf(t.quantity, lotSize)}</Secret>
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums text-subtle">
                          <Secret hidden={hide}>
                            {t.quantity.toLocaleString('en-US')}
                          </Secret>
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums">
                          <Secret hidden={hide}>{fmtPrice(t.price)}</Secret>
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums text-subtle">
                          <Secret hidden={hide}>{t.fees ? fmtPrice(t.fees) : '—'}</Secret>
                        </td>
                        <td className="px-4 py-2 text-subtle">
                          {t.note ? <Secret hidden={hide}>{t.note}</Secret> : ''}
                        </td>
                        <td className="px-4 py-2 text-right">
                          <button
                            onClick={() => remove.mutate(t.id)}
                            title="Delete transaction"
                            className="rounded p-2 text-muted transition hover:bg-bear/15 hover:text-bear"
                          >
                            <Trash2 size={14} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {adding && <TransactionModal onClose={() => setAdding(false)} />}
    </main>
  )
}
