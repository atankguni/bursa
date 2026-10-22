import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { addTransaction, type TransactionInput } from '../api'
import { usePreferences, useStatus, useStocks } from '../hooks'
import Modal from './Modal'

export default function TransactionModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const { data: stocks = [] } = useStocks([])
  const { data: status } = useStatus()
  const lotSize = status?.lot_size ?? 100
  const [ticker, setTicker] = useState('')
  const [side, setSide] = useState<'buy' | 'sell'>('buy')
  const [unit, setUnit] = useState<'lots' | 'shares'>('lots')
  const [quantity, setQuantity] = useState('')
  const [price, setPrice] = useState('')
  // Fee follows Settings → Trading costs until the user types their own.
  const [fees, setFees] = useState<string | null>(null)
  const { tradingCosts } = usePreferences()
  const [tradeDate, setTradeDate] = useState(new Date().toISOString().slice(0, 10))
  const [note, setNote] = useState('')

  // Quantity is stored as shares; lots are converted on submit.
  const shares =
    unit === 'lots' ? (Number(quantity) || 0) * lotSize : Number(quantity) || 0
  const feePct = side === 'buy' ? tradingCosts.buy_fee_pct : tradingCosts.sell_fee_pct
  const autoFee = Math.round((shares * (Number(price) || 0) * feePct) / 100)
  const fee = fees ?? String(autoFee)

  const add = useMutation({
    mutationFn: (input: TransactionInput) => addTransaction(input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['portfolio'] })
      onClose()
    },
  })

  const submit = () => {
    add.mutate({
      ticker: ticker.trim().toUpperCase(),
      side,
      quantity: shares,
      price: Number(price),
      fees: Number(fee) || 0,
      trade_date: tradeDate,
      note: note.trim() || null,
    })
  }

  const inputCls =
    'w-full rounded bg-panelalt px-3 py-2 text-sm text-ink ring-1 ring-line-strong outline-none focus:ring-accent'

  return (
    <Modal
      size="form"
      title="Add transaction"
      onClose={onClose}
      footer={
        <>
          <span />
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="rounded px-3 py-1.5 text-xs text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink"
            >
              Cancel
            </button>
            <button
              onClick={submit}
              disabled={add.isPending || !ticker || !quantity || !price}
              className="rounded bg-accent px-3 py-1.5 text-xs font-medium text-accent-ink transition hover:opacity-90 disabled:opacity-50"
            >
              {add.isPending ? 'Saving…' : 'Add'}
            </button>
          </div>
        </>
      }
    >
      <div className="space-y-3">
        <div>
          <label className="mb-1 block text-xs text-muted">Ticker</label>
          <input
            list="tickers"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="BBCA.JK"
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

        <div className="flex items-center gap-2">
          <span className="text-xs text-muted">Side</span>
          <div className="flex overflow-hidden rounded ring-1 ring-line-strong">
            {(['buy', 'sell'] as const).map((s) => (
              <button
                key={s}
                onClick={() => setSide(s)}
                className={`px-3 py-1.5 text-xs font-medium capitalize transition ${
                  side === s ? 'bg-active text-ink' : 'text-muted hover:text-ink'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <div className="mb-1 flex items-center justify-between">
              <label className="text-xs text-muted">Quantity</label>
              <div className="flex overflow-hidden rounded ring-1 ring-line-strong">
                {(['lots', 'shares'] as const).map((u) => (
                  <button
                    key={u}
                    onClick={() => setUnit(u)}
                    className={`px-2 py-0.5 text-[10px] font-medium capitalize transition ${
                      unit === u ? 'bg-active text-ink' : 'text-muted hover:text-ink'
                    }`}
                  >
                    {u}
                  </button>
                ))}
              </div>
            </div>
            <input
              type="number"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              className={inputCls}
            />
            {unit === 'lots' && quantity !== '' && (
              <p className="mt-1 text-[10px] text-subtle">
                = {shares.toLocaleString('en-US')} shares
              </p>
            )}
          </div>
          <div>
            <label className="mb-1 block text-xs text-muted">Price</label>
            <input
              type="number"
              value={price}
              onChange={(e) => setPrice(e.target.value)}
              className={inputCls}
            />
          </div>
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
          <div>
            <label className="mb-1 block text-xs text-muted">Date</label>
            <input
              type="date"
              value={tradeDate}
              onChange={(e) => setTradeDate(e.target.value)}
              className={inputCls}
            />
          </div>
        </div>

        <div>
          <label className="mb-1 block text-xs text-muted">Note (optional)</label>
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            className={inputCls}
          />
        </div>

        {add.isError && (
          <p className="text-xs text-bear">
            {(add.error as { response?: { data?: { detail?: string } } })?.response?.data
              ?.detail ?? 'Failed to add transaction.'}
          </p>
        )}
      </div>
    </Modal>
  )
}
