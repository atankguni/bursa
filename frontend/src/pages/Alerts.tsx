import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Bell, Trash2 } from 'lucide-react'
import { createAlert, deleteAlert, toggleAlert, type AlertType } from '../api'
import { useAlertEvents, useAlerts, useStocks } from '../hooks'

const TYPES: { value: AlertType; label: string }[] = [
  { value: 'price_above', label: 'Price above' },
  { value: 'price_below', label: 'Price below' },
  { value: 'pct_change', label: '% change ≥' },
  { value: 'rating_change', label: 'Rating change' },
]
const THRESHOLD_TYPES: AlertType[] = ['price_above', 'price_below', 'pct_change']

const inputCls =
  'rounded bg-panelalt/70 px-2.5 py-1.5 text-xs text-ink ring-1 ring-line-strong outline-none focus:ring-bull'

export default function Alerts() {
  const qc = useQueryClient()
  const { data: stocks = [] } = useStocks([])
  const { data: alerts = [] } = useAlerts()
  const { data: events = [] } = useAlertEvents()

  const [ticker, setTicker] = useState('')
  const [type, setType] = useState<AlertType>('price_above')
  const [threshold, setThreshold] = useState('')

  const invalidate = () => qc.invalidateQueries({ queryKey: ['alerts'] })
  const needsThreshold = THRESHOLD_TYPES.includes(type)

  const add = useMutation({
    mutationFn: () =>
      createAlert({
        ticker: ticker.trim().toUpperCase(),
        type,
        threshold: needsThreshold ? Number(threshold) : null,
      }),
    onSuccess: () => {
      invalidate()
      setTicker('')
      setThreshold('')
    },
  })
  const toggle = useMutation({ mutationFn: toggleAlert, onSuccess: invalidate })
  const remove = useMutation({ mutationFn: deleteAlert, onSuccess: invalidate })

  return (
    <main className="w-full animate-fade-in px-4 py-4">
      <div className="mb-3 flex items-center gap-2">
        <Bell size={16} className="text-bull" />
        <h2 className="text-sm font-semibold tracking-tight">Alerts</h2>
        <p className="text-[11px] text-subtle">
          In-app notifications — evaluated after each market sync
        </p>
      </div>

      <div className="space-y-3">
        {/* Create */}
        <div className="surface flex flex-wrap items-end gap-3 p-3">
          <div>
            <label className="mb-1 block text-[10px] uppercase tracking-wide text-subtle">
              Ticker
            </label>
            <input
              list="alert-tickers"
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              placeholder="BBCA.JK"
              className={`${inputCls} w-36`}
            />
            <datalist id="alert-tickers">
              {stocks.map((s) => (
                <option key={s.ticker} value={s.ticker}>
                  {s.name}
                </option>
              ))}
            </datalist>
          </div>
          <div>
            <label className="mb-1 block text-[10px] uppercase tracking-wide text-subtle">
              Condition
            </label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value as AlertType)}
              className={inputCls}
            >
              {TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>
          {needsThreshold && (
            <div>
              <label className="mb-1 block text-[10px] uppercase tracking-wide text-subtle">
                Threshold
              </label>
              <input
                type="number"
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
                className={`${inputCls} w-28`}
              />
            </div>
          )}
          <button
            onClick={() => add.mutate()}
            disabled={add.isPending || !ticker || (needsThreshold && !threshold)}
            className="rounded bg-bull px-3 py-1.5 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-50"
          >
            {add.isPending ? 'Adding…' : 'Add alert'}
          </button>
          {add.isError && (
            <span className="text-xs text-bear">
              {(add.error as { response?: { data?: { detail?: string } } })?.response
                ?.data?.detail ?? 'Failed'}
            </span>
          )}
        </div>

        {/* Rules */}
        <div className="surface overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full whitespace-nowrap text-left text-xs">
              <thead className="bg-panelalt/70 text-[10px] uppercase tracking-wider text-muted">
                <tr>
                  <th className="px-4 py-2.5">Ticker</th>
                  <th className="px-4 py-2.5">Condition</th>
                  <th className="px-4 py-2.5 text-right">Threshold</th>
                  <th className="px-4 py-2.5">Status</th>
                  <th className="px-4 py-2.5 text-center" />
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {alerts.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-10 text-center text-subtle">
                      No alerts yet.
                    </td>
                  </tr>
                )}
                {alerts.map((a) => (
                  <tr key={a.id} className="bg-panel">
                    <td className="px-4 py-2 font-semibold">
                      {a.ticker.replace('.JK', '')}
                    </td>
                    <td className="px-4 py-2 text-muted">
                      {TYPES.find((t) => t.value === a.type)?.label ?? a.type}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums text-muted">
                      {a.threshold ?? '—'}
                    </td>
                    <td className="px-4 py-2">
                      <button
                        onClick={() => toggle.mutate(a.id)}
                        className={`rounded px-2 py-0.5 text-[10px] font-medium ring-1 transition ${
                          a.active
                            ? 'bg-bull/15 text-bull ring-bull/30'
                            : 'text-subtle ring-line-strong'
                        }`}
                      >
                        {a.active ? 'Active' : 'Paused'}
                      </button>
                    </td>
                    <td className="px-4 py-2 text-center">
                      <button
                        onClick={() => remove.mutate(a.id)}
                        title="Delete"
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

        {/* Events */}
        <div className="surface overflow-hidden">
          <div className="border-b border-line px-4 py-2.5 text-[10px] uppercase tracking-wider text-muted">
            Recent triggers
          </div>
          <ul className="divide-y divide-line">
            {events.length === 0 && (
              <li className="px-4 py-6 text-center text-xs text-subtle">
                Nothing triggered yet.
              </li>
            )}
            {events.map((e) => (
              <li
                key={e.id}
                className="flex items-center justify-between gap-3 px-4 py-2"
              >
                <span className="text-xs text-ink">{e.message}</span>
                <span className="shrink-0 text-[10px] text-subtle">
                  {new Date(e.triggered_at).toLocaleString('en-GB', {
                    day: '2-digit',
                    month: 'short',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </main>
  )
}
