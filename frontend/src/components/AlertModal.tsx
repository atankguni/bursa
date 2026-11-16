import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { BellPlus } from 'lucide-react'
import { createAlert, type AlertType } from '../api'
import { errorMessage } from '../api/client'
import { ALERT_TYPES, THRESHOLD_TYPES } from '../lib/alertTypes'
import { useToast } from '../lib/toast'
import Modal from './Modal'

/** A new alert on one stock, from its pop-up (the Alerts page lists and manages them). */
export default function AlertModal({
  ticker,
  price,
  onClose,
}: {
  ticker: string
  /** Starts the price threshold here. */
  price: number | null
  onClose: () => void
}) {
  const qc = useQueryClient()
  const { toast } = useToast()
  const [type, setType] = useState<AlertType>('price_above')
  const [threshold, setThreshold] = useState(price != null ? String(price) : '')
  const needsThreshold = THRESHOLD_TYPES.includes(type)
  const isDividend = type === 'dividend_soon'

  const pick = (next: AlertType) => {
    setType(next)
    // A sensible starting number for each kind of condition.
    if (next === 'price_above' || next === 'price_below')
      setThreshold(price != null ? String(price) : '')
    else if (next === 'pct_change') setThreshold('5')
    else if (next === 'dividend_soon') setThreshold('3')
    else setThreshold('')
  }

  const add = useMutation({
    mutationFn: () =>
      createAlert({
        ticker,
        type,
        threshold:
          needsThreshold || (isDividend && threshold !== '') ? Number(threshold) : null,
      }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['alerts'] })
      toast(`Alert on ${ticker} added`)
      onClose()
    },
  })
  const invalid =
    needsThreshold && (threshold === '' || !Number.isFinite(Number(threshold)))

  return (
    <Modal
      size="form"
      title={`Alert · ${ticker}`}
      description="You'll be told on the Alerts page when it triggers."
      icon={<BellPlus size={18} />}
      onClose={onClose}
      footer={
        <>
          <span className="text-xs text-bear">
            {add.isError && errorMessage(add.error, "Couldn't add the alert.")}
          </span>
          <div className="flex gap-2">
            <button onClick={onClose} className="btn btn-secondary">
              Cancel
            </button>
            <button
              onClick={() => add.mutate()}
              disabled={add.isPending || invalid}
              className="btn btn-primary"
            >
              {add.isPending ? 'Adding…' : 'Add alert'}
            </button>
          </div>
        </>
      }
    >
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault()
          if (!invalid && !add.isPending) add.mutate()
        }}
      >
        <div>
          <label htmlFor="alert-type" className="field-label">
            Condition
          </label>
          <select
            id="alert-type"
            value={type}
            onChange={(e) => {
              const picked = ALERT_TYPES.find((t) => t.value === e.target.value)
              if (picked) pick(picked.value)
            }}
            className="input w-full"
          >
            {ALERT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>
        {(needsThreshold || isDividend) && (
          <div>
            <label htmlFor="alert-threshold" className="field-label">
              {isDividend
                ? 'Days before cum date'
                : type === 'pct_change'
                  ? 'Daily move, %'
                  : 'Price'}
            </label>
            <input
              id="alert-threshold"
              type="number"
              inputMode="decimal"
              min={isDividend ? 0 : undefined}
              max={isDividend ? 30 : undefined}
              value={threshold}
              onChange={(e) => setThreshold(e.target.value)}
              className="input w-full"
              autoFocus
            />
          </div>
        )}
        <p className="text-2xs text-subtle">
          {type === 'rating_change'
            ? "When Bursa's signal for this stock changes (for example from Hold to Buy)."
            : isDividend
              ? "Before the cum date, the last day to buy and still get the dividend. Dates are estimated from last year's; confirm with the company's announcement."
              : type === 'pct_change'
                ? 'When the price moves at least this much in a day, up or down.'
                : 'Checked after each market sync.'}
        </p>
      </form>
    </Modal>
  )
}
