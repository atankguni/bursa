import { useState, type ReactNode } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2, Wallet } from 'lucide-react'
import { addCashMovement, deleteCashMovement, type CashMovementInput } from '../api'
import { errorMessage } from '../api/client'
import { useCash } from '../hooks'
import { fmtMoney, fmtMoneySigned } from '../lib/format'
import Modal from './Modal'

const MASK = '••••••'
const signed = fmtMoneySigned
const tone = (v: number | null | undefined) =>
  v == null || v === 0 ? 'text-ink' : v > 0 ? 'text-bull' : 'text-bear'
const fmtDay = (d: string) =>
  new Date(`${d}T00:00:00`).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })

function Figure({
  label,
  value,
  hint,
  className,
}: {
  label: string
  value: ReactNode
  hint?: ReactNode
  className?: string
}) {
  return (
    <div>
      <div className="text-2xs font-medium text-muted">{label}</div>
      <div
        className={`mt-0.5 text-sm font-semibold tabular-nums ${className ?? 'text-ink'}`}
      >
        {value}
      </div>
      {hint && <div className="text-2xs text-subtle">{hint}</div>}
    </div>
  )
}

/**
 * Cash in the trading account (RDN): derived from the deposits and withdrawals
 * recorded here, plus trades (sales arrive at T+2) and dividends. Also the return
 * on the money put in: account value against net deposits.
 */
export default function CashPanel({ hide }: { hide: boolean }) {
  const { data: cash } = useCash()
  const [adding, setAdding] = useState(false)
  const [showAll, setShowAll] = useState(false)
  const qc = useQueryClient()
  const remove = useMutation({
    mutationFn: deleteCashMovement,
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['portfolio'] }),
  })
  const money = (v: number, fmt: (v: number) => string = fmtMoney) =>
    hide ? MASK : fmt(v)

  if (!cash) return null
  const rows = showAll ? cash.movements : cash.movements.slice(0, 5)

  return (
    <div className="surface">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <span className="section-title inline-flex items-center gap-1.5">
          <Wallet size={13} /> Cash (RDN)
        </span>
        <button onClick={() => setAdding(true)} className="btn btn-secondary btn-sm">
          <Plus size={13} /> Deposit / withdrawal
        </button>
      </div>

      {!cash.tracked ? (
        <p className="px-4 py-4 text-xs text-subtle">
          Record the money you moved into your trading account (and out of it), and Bursa
          works out your cash from your trades and dividends: what&apos;s available,
          what&apos;s still settling, and your return on the money you actually put in.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-x-4 gap-y-4 px-4 py-4 sm:grid-cols-4 sm:px-5">
            <Figure
              label="Cash available"
              value={money(cash.available)}
              className={cash.available < 0 ? 'text-bear' : 'text-ink'}
              hint={
                cash.available < 0
                  ? 'Below zero: a deposit or a sale may be missing'
                  : undefined
              }
            />
            <Figure
              label="Settling"
              value={money(cash.settling)}
              hint={
                cash.settles_on
                  ? `Sales, arriving by ${fmtDay(cash.settles_on)}`
                  : 'Sales at T+2'
              }
            />
            <Figure
              label="Account value"
              value={money(cash.account_value)}
              hint="Shares at the last price + cash"
            />
            <Figure
              label="Gain on deposits"
              value={
                <>
                  {money(cash.gain, signed)}
                  {cash.gain_pct != null && (
                    <span className="font-normal">
                      {' '}
                      ({cash.gain_pct > 0 ? '+' : ''}
                      {cash.gain_pct.toFixed(2)}%)
                    </span>
                  )}
                </>
              }
              className={tone(cash.gain)}
              hint={
                cash.annual_return_pct != null
                  ? `${cash.annual_return_pct > 0 ? '+' : ''}${cash.annual_return_pct.toFixed(1)}% a year, money-weighted`
                  : `Net deposits ${money(cash.net_deposits)}`
              }
            />
          </div>

          <div className="relative overflow-x-auto border-t border-line">
            <table className="w-full whitespace-nowrap text-left text-xs">
              <tbody className="divide-y divide-line">
                {rows.map((m) => (
                  <tr key={m.id} className="bg-panel">
                    <td className="px-4 py-2 text-muted">{m.day}</td>
                    <td
                      className={`px-4 py-2 font-medium ${
                        m.kind === 'deposit' ? 'text-bull' : 'text-bear'
                      }`}
                    >
                      {m.kind === 'deposit' ? 'Deposit' : 'Withdrawal'}
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      {money(m.kind === 'deposit' ? m.amount : -m.amount, signed)}
                    </td>
                    <td className="w-full px-4 py-2 text-subtle">
                      {m.note && !hide ? m.note : ''}
                    </td>
                    <td className="px-2 py-1 text-right">
                      <button
                        onClick={() => {
                          if (confirm(`Delete this ${m.kind}?`)) remove.mutate(m.id)
                        }}
                        className="rounded-sm p-2 text-subtle transition hover:bg-panelalt hover:text-bear"
                        aria-label={`Delete ${m.kind} of ${m.day}`}
                      >
                        <Trash2 size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {cash.movements.length > 5 && (
            <button
              onClick={() => setShowAll((v) => !v)}
              className="w-full border-t border-line px-4 py-2 text-xs text-accent hover:underline"
            >
              {showAll ? 'Show fewer' : `Show all ${cash.movements.length}`}
            </button>
          )}
        </>
      )}

      {adding && <CashModal onClose={() => setAdding(false)} />}
    </div>
  )
}

function CashModal({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const [kind, setKind] = useState<CashMovementInput['kind']>('deposit')
  const [amount, setAmount] = useState('')
  const [day, setDay] = useState(new Date().toLocaleDateString('en-CA'))
  const [note, setNote] = useState('')
  const add = useMutation({
    mutationFn: addCashMovement,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['portfolio'] })
      onClose()
    },
  })
  const value = Number(amount)
  const inputCls = 'input'

  return (
    <Modal
      size="form"
      title="Deposit or withdrawal"
      onClose={onClose}
      footer={
        <>
          <span />
          <div className="flex gap-2">
            <button onClick={onClose} className="btn btn-secondary">
              Cancel
            </button>
            <button
              onClick={() =>
                add.mutate({ kind, amount: value, day, note: note.trim() || null })
              }
              disabled={add.isPending || !(value > 0) || !day}
              className="btn btn-primary"
            >
              {add.isPending ? 'Saving…' : 'Add'}
            </button>
          </div>
        </>
      }
    >
      <div className="space-y-3">
        <div
          role="radiogroup"
          aria-label="Type"
          className="segmented grid w-full grid-cols-2"
        >
          {(['deposit', 'withdrawal'] as const).map((k) => (
            <button
              key={k}
              type="button"
              role="radio"
              aria-checked={kind === k}
              onClick={() => setKind(k)}
              className={`segment capitalize ${kind === k ? 'active' : ''}`}
            >
              {k}
            </button>
          ))}
        </div>
        <p className="text-2xs text-subtle">
          {kind === 'deposit'
            ? 'Money you transferred into your RDN (trading account).'
            : 'Money you took out of your RDN to your own bank account.'}{' '}
          Trades and dividends are counted automatically: don&apos;t record them here.
        </p>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="cash-amount" className="field-label">
              Amount (Rp)
            </label>
            <input
              id="cash-amount"
              type="number"
              min={1}
              inputMode="numeric"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className={inputCls}
            />
            {value > 0 && (
              <p className="mt-1 text-2xs text-subtle">= Rp {fmtMoney(value)}</p>
            )}
          </div>
          <div>
            <label htmlFor="cash-day" className="field-label">
              Date
            </label>
            <input
              id="cash-day"
              type="date"
              value={day}
              onChange={(e) => setDay(e.target.value)}
              className={inputCls}
            />
          </div>
        </div>
        <div>
          <label htmlFor="cash-note" className="field-label">
            Note (optional)
          </label>
          <input
            id="cash-note"
            value={note}
            maxLength={255}
            onChange={(e) => setNote(e.target.value)}
            className={inputCls}
          />
        </div>
        {add.isError && (
          <p className="text-xs text-bear">
            {errorMessage(add.error, 'Failed to save.')}
          </p>
        )}
      </div>
    </Modal>
  )
}
