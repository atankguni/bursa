import type { RecommendationSummary } from '../api'

/** Colour for a rating label (shared across Home / Watchlist / panels). */
export const signalTone = (rating: string) =>
  rating === 'Strong Buy' || rating === 'Buy'
    ? 'text-bull'
    : rating === 'Reduce' || rating === 'Avoid'
      ? 'text-bear'
      : 'text-muted'

const STRENGTH_DOTS: Record<string, number> = {
  Weak: 1,
  Moderate: 2,
  Strong: 3,
  'Very Strong': 4,
}

/** Compact rating + score + conviction pill for table cells. */
export default function SignalBadge({ rec }: { rec?: RecommendationSummary | null }) {
  if (!rec) return <span className="text-subtle">—</span>
  const dots = STRENGTH_DOTS[rec.strength] ?? 0
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded bg-panelalt/70 px-2 py-0.5 ring-1 ring-line"
      title={`Score ${rec.score.toFixed(0)}/100 · conviction ${rec.strength} · relative to the tracked universe`}
    >
      <span className={`text-[11px] font-semibold ${signalTone(rec.rating)}`}>
        {rec.rating}
      </span>
      <span className="text-[10px] tabular-nums text-subtle">{rec.score.toFixed(0)}</span>
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
