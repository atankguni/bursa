import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { deleteNote, saveNote, type HoldingNote, type HoldingNoteInput } from '../api'
import { errorMessage } from '../api/client'
import { queryKeys } from '../hooks'
import { fmtPrice } from '../lib/format'
import Modal from './Modal'

/** Today + `months`, as YYYY-MM-DD in local time. */
function monthsAhead(months: number): string {
  const d = new Date()
  d.setMonth(d.getMonth() + months)
  return d.toLocaleDateString('en-CA')
}

const REVIEW_PRESETS: { label: string; months: number }[] = [
  { label: '1 month', months: 1 },
  { label: '3 months', months: 3 },
  { label: '6 months', months: 6 },
  { label: '1 year', months: 12 },
]

export const FLAG_TEXT: Record<HoldingNote['flags'][number], string> = {
  review_due: 'review date reached',
  target_reached: 'at or above your target',
  stop_hit: 'at or below your stop',
}

/**
 * Your note on a stock: why you own it, the price where you'd take profit
 * (target) or cut the loss (stop), and when to look again. The daily email
 * reminds you when one of them is reached.
 */
export default function NoteModal({
  ticker,
  note,
  price,
  onClose,
}: {
  ticker: string
  note: HoldingNote | undefined
  price: number | null
  onClose: () => void
}) {
  const qc = useQueryClient()
  const [thesis, setThesis] = useState(note?.thesis ?? '')
  const [target, setTarget] = useState(note?.target != null ? String(note.target) : '')
  const [stop, setStop] = useState(note?.stop != null ? String(note.stop) : '')
  const [reviewOn, setReviewOn] = useState(note?.review_on ?? '')
  const done = () => {
    void qc.invalidateQueries({ queryKey: queryKeys.notes })
    onClose()
  }
  const save = useMutation({
    mutationFn: (input: HoldingNoteInput) => saveNote(ticker, input),
    onSuccess: done,
  })
  const remove = useMutation({ mutationFn: () => deleteNote(ticker), onSuccess: done })

  const targetN = target === '' ? null : Number(target)
  const stopN = stop === '' ? null : Number(stop)
  const invalid =
    (targetN != null && !(targetN > 0)) ||
    (stopN != null && !(stopN > 0)) ||
    (targetN != null && stopN != null && stopN >= targetN)
  const away = (level: number | null) =>
    price && level
      ? `${((level / price - 1) * 100).toFixed(1)}% from the last price`
      : null

  const inputCls =
    'w-full rounded-sm bg-panelalt px-3 py-2 text-sm text-ink ring-1 ring-line-strong outline-hidden focus:ring-accent'

  return (
    <Modal
      size="form"
      title={`Note · ${ticker}`}
      onClose={onClose}
      footer={
        <>
          {note ? (
            <button
              onClick={() => {
                if (confirm(`Delete your note on ${ticker}?`)) remove.mutate()
              }}
              className="rounded-sm px-3 py-1.5 text-xs text-bear ring-1 ring-line-strong transition hover:bg-panelalt"
            >
              Delete
            </button>
          ) : (
            <span />
          )}
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="rounded-sm px-3 py-1.5 text-xs text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink"
            >
              Cancel
            </button>
            <button
              onClick={() =>
                save.mutate({
                  thesis: thesis.trim() || null,
                  target: targetN,
                  stop: stopN,
                  review_on: reviewOn || null,
                })
              }
              disabled={save.isPending || invalid}
              className="rounded-sm bg-accent px-3 py-1.5 text-xs font-medium text-accent-ink transition hover:opacity-90 disabled:opacity-50"
            >
              {save.isPending ? 'Saving…' : 'Save'}
            </button>
          </div>
        </>
      }
    >
      <div className="space-y-3">
        {note && note.flags.length > 0 && (
          <p className="rounded-sm bg-amber-500/10 px-3 py-2 text-xs text-amber-700 ring-1 ring-amber-500/20 dark:text-amber-400">
            Needs a look: {note.flags.map((f) => FLAG_TEXT[f]).join(', ')}. Does your
            reason still hold? Update the note, or set a new review date.
          </p>
        )}
        <div>
          <label htmlFor="note-thesis" className="mb-1 block text-xs text-muted">
            Why you own it
          </label>
          <textarea
            id="note-thesis"
            rows={4}
            maxLength={2000}
            value={thesis}
            onChange={(e) => setThesis(e.target.value)}
            placeholder="e.g. Steady earnings growth, dividend yield above 5%; sell if margins keep falling."
            className={inputCls}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="note-target" className="mb-1 block text-xs text-muted">
              Target price
            </label>
            <input
              id="note-target"
              type="number"
              min={1}
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              className={inputCls}
            />
            <p className="mt-1 text-[10px] text-subtle">
              {away(targetN) ?? 'Where you would take profit'}
            </p>
          </div>
          <div>
            <label htmlFor="note-stop" className="mb-1 block text-xs text-muted">
              Stop price
            </label>
            <input
              id="note-stop"
              type="number"
              min={1}
              value={stop}
              onChange={(e) => setStop(e.target.value)}
              className={inputCls}
            />
            <p className={`mt-1 text-[10px] ${invalid ? 'text-bear' : 'text-subtle'}`}>
              {targetN != null && stopN != null && stopN >= targetN
                ? 'Must be below the target'
                : (away(stopN) ?? 'Where you would cut the loss')}
            </p>
          </div>
        </div>
        <div>
          <label htmlFor="note-review" className="mb-1 block text-xs text-muted">
            Review on
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <input
              id="note-review"
              type="date"
              value={reviewOn}
              onChange={(e) => setReviewOn(e.target.value)}
              className={`${inputCls} w-auto`}
            />
            {REVIEW_PRESETS.map((p) => (
              <button
                key={p.months}
                type="button"
                onClick={() => setReviewOn(monthsAhead(p.months))}
                className="rounded-sm px-2 py-1 text-[11px] text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink"
              >
                +{p.label}
              </button>
            ))}
          </div>
        </div>
        <p className="text-[11px] text-subtle">
          The Portfolio page flags the stock, and the daily email (Settings → Investing)
          reminds you, on the review date or when the last close reaches the target or the
          stop{price ? ` (last close Rp ${fmtPrice(price)})` : ''}. Prices are as they are
          now: after a stock split, update them.
        </p>
        {(save.isError || remove.isError) && (
          <p className="text-xs text-bear">
            {errorMessage(save.error ?? remove.error, 'Failed to save.')}
          </p>
        )}
      </div>
    </Modal>
  )
}
