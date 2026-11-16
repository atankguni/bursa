import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { addTransaction, type TransactionInput } from '../api'
import { usePreferences, useStatus, useStocks } from '../hooks'
import Modal from './Modal'
import { errorMessage } from '../api/client'
import { useToast } from '../lib/toast'
import { fmtNum } from '../lib/format'
import { useSettings } from '../lib/settings'

/** What the form records: trades, plus shares received from corporate actions. */
type Entry = 'buy' | 'sell' | 'rights' | 'bonus'

const ENTRIES: { id: Entry; label: string; hint?: string }[] = [
  { id: 'buy', label: 'Buy' },
  { id: 'sell', label: 'Sell' },
  {
    id: 'rights',
    label: 'Rights issue',
    hint: 'New shares from an exercised rights issue (HMETD), at the exercise price. They blend into your average cost. Use the date the new shares arrived.',
  },
  {
    id: 'bonus',
    label: 'Bonus shares',
    hint: 'Free shares (saham bonus, or a stock dividend): your total cost stays the same, so the average per share falls. Use the ex-date.',
  },
]

export default function TransactionModal({
  onClose,
  initial,
}: {
  onClose: () => void
  /** Pre-filled trade, e.g. from the sell calculator. */
  initial?: { ticker: string; side: 'buy' | 'sell'; lots?: number; price?: number | null }
}) {
  const qc = useQueryClient()
  const { data: stocks = [] } = useStocks([])
  const { data: status } = useStatus()
  const lotSize = status?.lot_size ?? 100
  const [ticker, setTicker] = useState(initial?.ticker ?? '')
  const [entry, setEntry] = useState<Entry>(initial?.side ?? 'buy')
  const side = entry === 'sell' ? 'sell' : 'buy'
  const free = entry === 'bonus' // no price, no fees
  const { settings } = useSettings()
  // Settings → Investing → Enter trades in.
  const [unit, setUnit] = useState<'lots' | 'shares'>(settings.tradeUnit)
  const [quantity, setQuantity] = useState(
    initial?.lots == null
      ? ''
      : String(settings.tradeUnit === 'lots' ? initial.lots : initial.lots * lotSize),
  )
  const [price, setPrice] = useState(initial?.price != null ? String(initial.price) : '')
  // Fee follows Settings → Trading costs until the user types their own.
  const [fees, setFees] = useState<string | null>(null)
  const { tradingCosts } = usePreferences()
  const [tradeDate, setTradeDate] = useState(new Date().toISOString().slice(0, 10))
  const [note, setNote] = useState('')

  // Quantity is stored as shares; lots are converted on submit.
  const shares =
    unit === 'lots' ? (Number(quantity) || 0) * lotSize : Number(quantity) || 0
  // Exercising rights goes through the registrar, not a trade: no broker fee by default.
  const feePct =
    entry === 'rights'
      ? 0
      : side === 'buy'
        ? tradingCosts.buy_fee_pct
        : tradingCosts.sell_fee_pct
  const autoFee = Math.round((shares * (Number(price) || 0) * feePct) / 100)
  const fee = fees ?? String(autoFee)

  const { toast } = useToast()
  const add = useMutation({
    mutationFn: (input: TransactionInput) => addTransaction(input),
    onSuccess: (_d, input) => {
      void qc.invalidateQueries({ queryKey: ['portfolio'] })
      const what =
        input.kind === 'rights'
          ? 'rights issue'
          : input.kind === 'bonus'
            ? 'bonus shares'
            : input.side
      toast(`${input.ticker} ${what} saved`)
      onClose()
    },
  })

  const submit = () => {
    add.mutate({
      ticker: ticker.trim().toUpperCase(),
      side,
      kind: entry === 'rights' ? 'rights' : entry === 'bonus' ? 'bonus' : 'trade',
      quantity: shares,
      price: free ? 0 : Number(price),
      fees: free ? 0 : Number(fee) || 0,
      trade_date: tradeDate,
      note: note.trim() || null,
    })
  }

  const inputCls = 'input'

  return (
    <Modal
      size="form"
      title="Add transaction"
      onClose={onClose}
      footer={
        <>
          <span />
          <div className="flex gap-2">
            <button onClick={onClose} className="btn btn-secondary">
              Cancel
            </button>
            <button
              onClick={submit}
              disabled={add.isPending || !ticker || !quantity || (!free && !price)}
              className="btn btn-primary"
            >
              {add.isPending ? 'Saving…' : 'Add'}
            </button>
          </div>
        </>
      }
    >
      <div className="space-y-3">
        <div>
          <label className="field-label">Ticker</label>
          <input
            list="tickers"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="BBCA"
            className={inputCls}
          />
          <datalist id="tickers">
            {stocks.map((s) => (
              <option key={s.ticker} value={s.ticker}>
                {s.name}
              </option>
            ))}
          </datalist>
        </div>

        <div>
          <span className="field-label" id="tx-type">
            Type
          </span>
          <div
            role="radiogroup"
            aria-labelledby="tx-type"
            className="segmented grid w-full grid-cols-2 sm:grid-cols-4"
          >
            {ENTRIES.map((e) => (
              <button
                key={e.id}
                type="button"
                role="radio"
                aria-checked={entry === e.id}
                onClick={() => setEntry(e.id)}
                className={`segment ${entry === e.id ? 'active' : ''}`}
              >
                {e.label}
              </button>
            ))}
          </div>
          {ENTRIES.find((e) => e.id === entry)?.hint && (
            <p className="mt-1 text-2xs text-subtle">
              {ENTRIES.find((e) => e.id === entry)?.hint}
            </p>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <div className="mb-1 flex items-center justify-between">
              <label className="text-xs text-muted">Quantity</label>
              <div className="segmented">
                {(['lots', 'shares'] as const).map((u) => (
                  <button
                    key={u}
                    onClick={() => setUnit(u)}
                    className={`segment capitalize ${unit === u ? 'active' : ''}`}
                  >
                    {u}
                  </button>
                ))}
              </div>
            </div>
            <input
              type="number"
              min={1}
              step={1}
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              className={inputCls}
            />
            {unit === 'lots' && quantity !== '' && (
              <p className="mt-1 text-2xs text-subtle">= {fmtNum(shares)} shares</p>
            )}
          </div>
          {!free && (
            <div>
              <label className="field-label">
                {entry === 'rights' ? 'Exercise price' : 'Price'}
              </label>
              <input
                type="number"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                className={inputCls}
              />
            </div>
          )}
          {!free && (
            <div>
              <label className="mb-1 flex justify-between text-xs text-muted">
                Fees
                {fees === null ? (
                  <span className="text-subtle">{feePct}% · auto</span>
                ) : (
                  <button
                    type="button"
                    onClick={() => setFees(null)}
                    className="text-accent hover:underline"
                  >
                    Use {feePct}%
                  </button>
                )}
              </label>
              <input
                type="number"
                value={fee}
                onChange={(e) => setFees(e.target.value)}
                className={inputCls}
              />
            </div>
          )}
          <div>
            <label className="field-label">Date</label>
            <input
              type="date"
              value={tradeDate}
              onChange={(e) => setTradeDate(e.target.value)}
              className={inputCls}
            />
          </div>
        </div>

        <div>
          <label className="field-label">Note (optional)</label>
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            className={inputCls}
          />
        </div>

        {add.isError && (
          <p className="text-xs text-bear">
            {errorMessage(add.error, 'Failed to add transaction.')}
          </p>
        )}
      </div>
    </Modal>
  )
}
