import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { BellRing, Trash2 } from 'lucide-react'
import EmptyState from '../components/ui/EmptyState'
import { createAlert, deleteAlert, toggleAlert, type AlertType } from '../api'
import { useAlertEvents, useAlerts, useStocks } from '../hooks'
import { useAuth } from '../lib/auth'
import { fmtShortDateTime } from '../lib/format'
import NotificationsCard from '../components/NotificationsCard'
import { errorMessage } from '../api/client'
import { useToast } from '../lib/toast'

const TYPES: { value: AlertType; label: string }[] = [
  { value: 'price_above', label: 'Price above' },
  { value: 'price_below', label: 'Price below' },
  { value: 'pct_change', label: '% change ≥' },
  { value: 'rating_change', label: 'Signal change' },
  { value: 'dividend_soon', label: 'Dividend coming up' },
]
const THRESHOLD_TYPES: AlertType[] = ['price_above', 'price_below', 'pct_change']

const inputCls = 'input input-sm'

export default function Alerts() {
  const qc = useQueryClient()
  const { isAdmin } = useAuth() // Telegram is the server owner's chat
  const { data: stocks = [] } = useStocks([])
  const { data: alerts = [] } = useAlerts()
  const { data: events = [] } = useAlertEvents()

  const [ticker, setTicker] = useState('')
  const [type, setType] = useState<AlertType>('price_above')
  const [threshold, setThreshold] = useState('')

  const invalidate = () => qc.invalidateQueries({ queryKey: ['alerts'] })
  const needsThreshold = THRESHOLD_TYPES.includes(type)
  const isDividend = type === 'dividend_soon'

  const add = useMutation({
    mutationFn: () =>
      createAlert({
        ticker: ticker.trim().toUpperCase(),
        type,
        threshold:
          needsThreshold || (isDividend && threshold !== '') ? Number(threshold) : null,
      }),
    onSuccess: () => {
      void invalidate()
      toast(`Alert on ${ticker.trim().toUpperCase()} added`)
      setTicker('')
      setThreshold('')
    },
  })
  const toggle = useMutation({ mutationFn: toggleAlert, onSuccess: invalidate })
  const { toast, deleteWithUndo, isDeleting } = useToast()
  const live = alerts.filter((a) => !isDeleting(`alert:${a.id}`))

  return (
    <main className="page">
      <div className="mb-5 lg:mb-6">
        <h2 className="page-title">Alerts</h2>
        <p className="page-sub">
          Evaluated after each market sync · shown here
          {isAdmin && ', and on Telegram if connected'}
        </p>
      </div>

      <div className="space-y-3">
        {isAdmin && <NotificationsCard />}

        {/* Create */}
        <div className="surface flex flex-wrap items-end gap-3 p-4">
          <div>
            <label className="field-label">Ticker</label>
            <input
              list="alert-tickers"
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              placeholder="BBCA"
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
            <label className="field-label">Condition</label>
            <select
              value={type}
              onChange={(e) => {
                const picked = TYPES.find((t) => t.value === e.target.value)
                if (picked) setType(picked.value)
              }}
              className={`${inputCls} w-auto`}
            >
              {TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>
          {(needsThreshold || isDividend) && (
            <div>
              <label className="field-label">
                {isDividend ? 'Days before cum date' : 'Threshold'}
              </label>
              <input
                type="number"
                min={isDividend ? 0 : undefined}
                max={isDividend ? 30 : undefined}
                placeholder={isDividend ? '3' : undefined}
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
                className={`${inputCls} w-28`}
              />
            </div>
          )}
          <button
            onClick={() => add.mutate()}
            disabled={add.isPending || !ticker || (needsThreshold && !threshold)}
            className="btn btn-primary h-8"
          >
            {add.isPending ? 'Adding…' : 'Add alert'}
          </button>
          {add.isError && (
            <span className="text-xs text-bear">{errorMessage(add.error, 'Failed')}</span>
          )}
        </div>
        {isDividend && (
          <p className="-mt-1 mb-3 text-2xs text-subtle">
            Reminds you before the <span className="text-muted">cum date</span>, the last
            day to buy and still get the dividend. Dates are estimated from last
            year&apos;s ex-dates (IDX companies pay on regular schedules); confirm with
            the company&apos;s announcement before trading.
          </p>
        )}

        {/* Rules */}
        <div className="surface overflow-hidden">
          <div className="relative overflow-x-auto">
            <table className="w-full whitespace-nowrap text-left text-xs">
              <thead className="table-head">
                <tr>
                  <th className="px-4 py-2.5">Ticker</th>
                  <th className="px-4 py-2.5">Condition</th>
                  <th className="px-4 py-2.5 text-right">Threshold</th>
                  <th className="px-4 py-2.5">Status</th>
                  <th className="px-4 py-2.5 text-center" />
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {live.length === 0 && (
                  <tr>
                    <td colSpan={5}>
                      <EmptyState icon={BellRing} title="No alerts yet">
                        Pick a stock and a condition above. You'll be told here (and by
                        email, if set up) when it happens.
                      </EmptyState>
                    </td>
                  </tr>
                )}
                {live.map((a) => (
                  <tr key={a.id} className="bg-panel">
                    <td className="px-4 py-2 font-semibold">{a.ticker}</td>
                    <td className="px-4 py-2 text-muted">
                      {TYPES.find((t) => t.value === a.type)?.label ?? a.type}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums text-muted">
                      {a.type === 'dividend_soon'
                        ? `${a.threshold ?? 3} days ahead`
                        : (a.threshold ?? '—')}
                    </td>
                    <td className="px-4 py-2">
                      <button
                        onClick={() => toggle.mutate(a.id)}
                        className={`rounded-sm px-2 py-0.5 text-2xs font-medium ring-1 transition ${
                          a.active
                            ? 'bg-accent/15 text-accent ring-accent/30'
                            : 'text-subtle ring-line-strong'
                        }`}
                      >
                        {a.active ? 'Active' : 'Paused'}
                      </button>
                    </td>
                    <td className="px-4 py-2 text-center">
                      <button
                        onClick={() =>
                          deleteWithUndo({
                            key: `alert:${a.id}`,
                            label: `Alert on ${a.ticker}`,
                            commit: () => deleteAlert(a.id),
                            onDone: invalidate,
                          })
                        }
                        title="Delete"
                        className="rounded-sm p-2 text-muted transition hover:bg-bear/15 hover:text-bear"
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
          <div className="section-title border-b border-line px-4 py-3">
            Recent triggers
          </div>
          <ul className="divide-y divide-line">
            {events.length === 0 && (
              <li className="px-4 py-8 text-center text-xs text-subtle">
                Nothing triggered yet.
              </li>
            )}
            {events.map((e) => (
              <li
                key={e.id}
                className="flex items-center justify-between gap-3 px-4 py-2"
              >
                <span className="text-xs text-ink">{e.message}</span>
                <span className="shrink-0 text-2xs text-subtle">
                  {fmtShortDateTime(e.triggered_at)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </main>
  )
}
