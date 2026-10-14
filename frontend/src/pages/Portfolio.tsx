import { lazy, Suspense, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'
import { deleteTransaction } from '../api'
import { usePortfolio, usePortfolioHistory, useTransactions } from '../hooks'
import { useSettings } from '../lib/settings'
import { fmtPrice } from '../lib/format'
import TransactionModal from '../components/TransactionModal'

const PortfolioChart = lazy(() => import('../components/PortfolioChart'))

const signed = (v: number | null) =>
  v == null ? '—' : `${v > 0 ? '+' : ''}${fmtPrice(v)}`
const signedPct = (v: number | null) =>
  v == null ? '—' : `${v > 0 ? '+' : ''}${v.toFixed(2)}%`

function Card({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="surface px-4 py-3">
      <div className="text-[10px] uppercase tracking-wider text-muted">{label}</div>
      <div className={`mt-1 text-lg font-semibold tabular-nums ${tone ?? 'text-ink'}`}>
        {value}
      </div>
    </div>
  )
}

export default function Portfolio() {
  const [adding, setAdding] = useState(false)
  const qc = useQueryClient()
  const { settings } = useSettings()
  const { data: pf, isLoading } = usePortfolio()
  const { data: txs = [] } = useTransactions()
  const { data: history = [] } = usePortfolioHistory()

  const remove = useMutation({
    mutationFn: deleteTransaction,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['portfolio'] }),
  })

  const tone = (v: number | null | undefined) => {
    if (!settings.colorizeChanges || v == null || v === 0) return 'text-muted'
    return v > 0 ? 'text-bull' : 'text-bear'
  }

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
        <button
          onClick={() => setAdding(true)}
          className="inline-flex items-center gap-1.5 rounded-full bg-bull px-3 py-1.5 text-xs font-medium text-white transition hover:opacity-90"
        >
          <Plus size={14} /> Add transaction
        </button>
      </div>

      {isLoading ? (
        <div className="surface px-4 py-10 text-center text-subtle">Loading…</div>
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            <Card label="Market value" value={fmtPrice(totals?.market_value ?? 0)} />
            <Card
              label="Unrealized P/L"
              value={`${signed(totals?.unrealized_pl ?? 0)} (${signedPct(
                totals?.unrealized_pl_pct ?? null,
              )})`}
              tone={tone(totals?.unrealized_pl)}
            />
            <Card
              label="Day change"
              value={`${signed(totals?.day_change ?? 0)} (${signedPct(
                totals?.day_change_pct ?? null,
              )})`}
              tone={tone(totals?.day_change)}
            />
            <Card label="Invested" value={fmtPrice(totals?.invested ?? 0)} />
            <Card
              label="Realized P/L"
              value={signed(totals?.realized_pl ?? 0)}
              tone={tone(totals?.realized_pl)}
            />
            <Card
              label="Est. annual income"
              value={fmtPrice(totals?.projected_income ?? 0)}
            />
          </div>

          {/* Holdings */}
          <div className="surface overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full whitespace-nowrap text-left text-xs">
                <thead className="bg-panelalt/70 text-[10px] uppercase tracking-wider text-muted">
                  <tr>
                    <th className="px-4 py-2.5">Ticker</th>
                    <th className="px-4 py-2.5 text-right">Qty</th>
                    <th className="px-4 py-2.5 text-right">Avg</th>
                    <th className="px-4 py-2.5 text-right">Price</th>
                    <th className="px-4 py-2.5 text-right">Value</th>
                    <th className="px-4 py-2.5 text-right">P/L</th>
                    <th className="px-4 py-2.5 text-right">P/L %</th>
                    <th className="px-4 py-2.5 text-right">Day %</th>
                    <th className="px-4 py-2.5 text-right">Weight</th>
                    <th className="px-4 py-2.5 text-right">Est. income</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {holdings.length === 0 && (
                    <tr>
                      <td colSpan={10} className="px-4 py-10 text-center text-subtle">
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
                        {h.ticker.replace('.JK', '')}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">{h.quantity}</td>
                      <td className="px-4 py-2 text-right tabular-nums text-muted">
                        {fmtPrice(h.avg_cost)}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {fmtPrice(h.price)}
                      </td>
                      <td className="px-4 py-2 text-right font-medium tabular-nums">
                        {fmtPrice(h.market_value)}
                      </td>
                      <td
                        className={`px-4 py-2 text-right tabular-nums ${tone(h.unrealized_pl)}`}
                      >
                        {signed(h.unrealized_pl)}
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
                        {h.projected_income ? fmtPrice(h.projected_income) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Equity curve */}
          {history.length > 1 && (
            <div className="surface p-4">
              <div className="mb-2 text-[10px] uppercase tracking-wider text-muted">
                Portfolio value
              </div>
              <Suspense
                fallback={
                  <div className="h-[260px] animate-pulse rounded-lg bg-panelalt" />
                }
              >
                <PortfolioChart data={history} />
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
                          {t.quantity}
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums">
                          {fmtPrice(t.price)}
                        </td>
                        <td className="px-4 py-2 text-right tabular-nums text-subtle">
                          {t.fees ? fmtPrice(t.fees) : '—'}
                        </td>
                        <td className="px-4 py-2 text-subtle">{t.note ?? ''}</td>
                        <td className="px-4 py-2 text-right">
                          <button
                            onClick={() => remove.mutate(t.id)}
                            title="Delete transaction"
                            className="rounded-md p-1.5 text-muted transition hover:bg-bear/15 hover:text-bear"
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
