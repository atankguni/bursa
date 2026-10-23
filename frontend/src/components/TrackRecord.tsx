import type { RatingRecord, TrackRecord as TrackRecordData } from '../api'
import { useTrackRecord } from '../hooks'
import { RATING_ORDER, ratingLabel, ratingTone } from '../lib/ratings'

const HORIZON_TEXT: { [h: string]: string } = {
  '3m': 'the next 3 months',
  '4w': 'the next 4 weeks',
}

const fmtDay = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })

/** Plain words for the rank correlation (rule of thumb from the backtest docs). */
const edgeWord = (ic: number) =>
  ic < 0.03 ? 'none to speak of' : ic < 0.07 ? 'small' : ic < 0.12 ? 'modest' : 'good'

/** Bars grow left or right of the 50% (coin-flip) line; ±20 points fills a side. */
function BeatRow({ row, current }: { row: RatingRecord; current: boolean }) {
  const pct = row.beat * 100
  const side = Math.min(Math.abs(pct - 50) / 20, 1) * 50
  return (
    <div
      className={`flex items-center gap-3 rounded-sm px-1.5 py-0.5 text-xs ${
        current ? 'bg-panelalt ring-1 ring-line-strong' : ''
      }`}
    >
      <span
        className={`w-24 shrink-0 ${current ? 'font-semibold' : ''} ${ratingTone(row.rating)}`}
      >
        {ratingLabel(row.rating)}
      </span>
      <div className="relative h-2 flex-1 rounded-xs bg-panelalt">
        <div
          className={`absolute inset-y-0 rounded-xs ${pct >= 50 ? 'bg-bull' : 'bg-bear'}`}
          style={
            pct >= 50
              ? { left: '50%', width: `${side}%` }
              : { right: '50%', width: `${side}%` }
          }
        />
        <div className="absolute inset-y-[-2px] left-1/2 w-px bg-line-strong" />
      </div>
      <span className="w-9 text-right font-medium tabular-nums text-ink">
        {pct.toFixed(0)}%
      </span>
      <span className="hidden w-16 text-right text-[10px] tabular-nums text-subtle sm:inline">
        n={row.n.toLocaleString()}
      </span>
    </div>
  )
}

function Rows({ rows, current }: { rows: RatingRecord[]; current?: string | undefined }) {
  const sorted = [...rows].sort(
    (a, b) => RATING_ORDER.indexOf(a.rating) - RATING_ORDER.indexOf(b.rating),
  )
  return (
    <div className="space-y-0.5">
      {sorted.map((r) => (
        <BeatRow key={r.rating} row={r} current={r.rating === current} />
      ))}
    </div>
  )
}

function Live({
  live,
  current,
}: {
  live: TrackRecordData['live']
  current?: string | undefined
}) {
  if (live.ratings.length > 0 && live.since) {
    return (
      <div className="space-y-1.5">
        <p className="text-[11px] text-muted">
          <span className="font-medium text-ink">Live record</span> since{' '}
          {fmtDay(live.since)} ({live.matured_days} days with a result so far):
        </p>
        <Rows rows={live.ratings} current={current} />
      </div>
    )
  }
  return (
    <p className="text-[11px] text-subtle">
      <span className="font-medium text-muted">Live record:</span>{' '}
      {live.since && live.ready_on
        ? `ratings are saved every trading day since ${fmtDay(live.since)}; the first results arrive around ${fmtDay(live.ready_on)}.`
        : 'ratings are saved at each day’s close; results appear once enough time has passed.'}
    </p>
  )
}

/** How often each rating beat the typical stock: backtest, then the live record. */
export default function TrackRecord({ current }: { current?: string | undefined }) {
  const { data } = useTrackRecord()
  if (!data) return null
  const { backtest, live } = data
  const horizon = HORIZON_TEXT[data.horizon] ?? data.horizon
  const weakYears = backtest
    ? Object.entries(backtest.years)
        .filter(([, ic]) => ic < 0.02)
        .map(([y]) => y)
    : []

  return (
    <section className="space-y-2 rounded-md px-3 py-2.5 ring-1 ring-line">
      <h4 className="text-[10px] uppercase tracking-wide text-muted">
        How have these ratings done?
      </h4>
      {backtest && (
        <>
          <p className="text-[11px] text-muted">
            How often a stock with each rating beat the typical (median) stock over{' '}
            {horizon}, testing this model on {backtest.start.slice(0, 4)}–
            {backtest.end.slice(0, 4)} prices ({backtest.universe}).{' '}
            <span className="text-ink">50% is a coin flip.</span>
          </p>
          <Rows rows={backtest.ratings} current={current} />
          <p className="text-[11px] text-subtle">
            Overall edge:{' '}
            <span className="font-medium text-muted">{edgeWord(backtest.ic)}</span>{' '}
            (score-to-return correlation {backtest.ic >= 0 ? '+' : ''}
            {backtest.ic.toFixed(2)})
            {weakYears.length > 0 && <>, and it didn’t work in {weakYears.join(', ')}</>}.
            A backtest only covers stocks still listed today and was run on data the model
            was tuned on, so treat it as a best case.
          </p>
        </>
      )}
      <Live live={live} current={current} />
    </section>
  )
}
