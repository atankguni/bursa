import type { RecommendationSummary } from '../api'
import { CONVICTION_DOTS, ratingLabel, ratingTone } from '../lib/ratings'
import { fmtNum } from '../lib/format'

/** Compact rating + score + conviction pill for table cells. */
export default function SignalBadge({ rec }: { rec?: RecommendationSummary | null }) {
  if (!rec) return <span className="text-subtle">—</span>
  const dots = CONVICTION_DOTS[rec.strength]
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-sm bg-panelalt px-2 py-0.5"
      title={`Score ${fmtNum(rec.score)}/100 · conviction ${rec.strength} · ranked against the other stocks, not advice`}
    >
      <span className={`text-2xs font-semibold ${ratingTone(rec.rating)}`}>
        {ratingLabel(rec.rating)}
      </span>
      <span className="text-2xs tabular-nums text-subtle">{fmtNum(rec.score)}</span>
      <span className="inline-flex gap-0.5">
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className={`h-1 w-1 rounded-full ${i < dots ? 'bg-ink' : 'bg-active'}`}
          />
        ))}
      </span>
    </span>
  )
}
