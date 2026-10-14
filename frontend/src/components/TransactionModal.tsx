import { useState } from 'react'
import { createPortal } from 'react-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { addTransaction, type TransactionInput } from '../api'
import { useStocks } from '../hooks'

export default function TransactionModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const { data: stocks = [] } = useStocks([])
  const [ticker, setTicker] = useState('')
  const [side, setSide] = useState<'buy' | 'sell'>('buy')
  const [quantity, setQuantity] = useState('')
  const [price, setPrice] = useState('')
  const [fees, setFees] = useState('0')
  const [tradeDate, setTradeDate] = useState(new Date().toISOString().slice(0, 10))
  const [note, setNote] = useState('')

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
      quantity: Number(quantity),
      price: Number(price),
      fees: Number(fees) || 0,
      trade_date: tradeDate,
      note: note.trim() || null,
    })
  }

  const inputCls =
    'w-full rounded-lg bg-panelalt px-3 py-2 text-sm text-ink ring-1 ring-line outline-none focus:ring-bull'

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md animate-fade-in rounded-2xl bg-panel p-6 shadow-pop ring-1 ring-line"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Add transaction</h2>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-muted transition hover:bg-panelalt hover:text-ink"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>

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
            <div className="flex overflow-hidden rounded-lg ring-1 ring-line">
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
              <label className="mb-1 block text-xs text-muted">Quantity</label>
              <input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                className={inputCls}
              />
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
              <label className="mb-1 block text-xs text-muted">Fees</label>
              <input
                type="number"
                value={fees}
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
              {(add.error as { response?: { data?: { detail?: string } } })?.response
                ?.data?.detail ?? 'Failed to add transaction.'}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <button
              onClick={onClose}
              className="rounded-lg px-3 py-1.5 text-xs text-muted ring-1 ring-line transition hover:bg-panelalt hover:text-ink"
            >
              Cancel
            </button>
            <button
              onClick={submit}
              disabled={add.isPending || !ticker || !quantity || !price}
              className="rounded-lg bg-bull px-3 py-1.5 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-50"
            >
              {add.isPending ? 'Saving…' : 'Add'}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}
