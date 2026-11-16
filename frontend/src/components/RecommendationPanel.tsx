import { AlertCircle, Info } from 'lucide-react'
import type { InvestingStyle, Recommendation } from '../api'
import { usePreferences } from '../hooks'
import { CONVICTION_DOTS, ratingLabel, ratingTone } from '../lib/ratings'
import TrackRecord from './TrackRecord'
import Term from './Term'
import { categoryEntry } from '../lib/glossary'
import { fmtNum } from '../lib/format'

interface Props {
  data?: Recommendation | undefined
  isLoading: boolean
  isError?: boolean
}

const barTone = (score: number) =>
  score >= 65 ? 'bg-bull' : score <= 40 ? 'bg-bear' : 'bg-active'

const STYLE_LABEL: Record<InvestingStyle, string> = {
  investor: 'Investor view · long term',
  trader: 'Trader view · 1–4 weeks',
}

const NOT_RATED_HINT: Record<InvestingStyle, string> = {
  investor:
    'Investor signals need fundamentals. Open the Fundamentals tab to fetch them, then check back here.',
  trader:
    'Trader signals cover liquid stocks only (≥ Rp 1bn traded per day, 21+ days of prices).',
}

export default function RecommendationPanel({ data, isLoading, isError }: Props) {
  const { style } = usePreferences()
  if (isLoading) {
    return (
      <div className="flex h-[300px] items-center justify-center text-muted">
        Scoring…
      </div>
    )
  }
  if (isError || !data) {
    return (
      <div className="flex h-[300px] flex-col items-center justify-center gap-2 text-muted">
        <AlertCircle size={20} />
        <span className="text-sm">Not rated yet.</span>
        <span className="max-w-xs text-center text-2xs text-subtle">
          {NOT_RATED_HINT[style]}
        </span>
      </div>
    )
  }

  const dots = CONVICTION_DOTS[data.strength]

  return (
    <div className="space-y-4">
      {/* Headline */}
      <div className="flex flex-wrap items-center gap-4 rounded-md bg-panelalt/60 px-4 py-3">
        <div className="flex items-baseline gap-2">
          <span className={`text-3xl font-bold ${ratingTone(data.rating)}`}>
            {fmtNum(data.score)}
          </span>
          <span className="text-xs text-subtle">
            <Term id="score">/ 100</Term>
          </span>
        </div>
        <div className="flex flex-col">
          <span className={`text-sm font-semibold ${ratingTone(data.rating)}`}>
            <Term id="rating">{ratingLabel(data.rating)}</Term>
            <span className="ml-1.5 text-2xs font-normal text-subtle">
              vs. other stocks
            </span>
          </span>
          <span className="flex items-center gap-1 text-2xs text-muted">
            <Term id="conviction">Conviction: {data.strength}</Term>
            <span className="inline-flex gap-0.5">
              {[0, 1, 2, 3].map((i) => (
                <span
                  key={i}
                  className={`h-1.5 w-1.5 rounded-full ${
                    i < dots ? 'bg-ink' : 'bg-active'
                  }`}
                />
              ))}
            </span>
          </span>
        </div>
        <div className="ml-auto text-right text-2xs text-subtle">
          <div className="mb-1 inline-block rounded-xs bg-panel px-1.5 py-0.5 font-medium text-muted ring-1 ring-line">
            {STYLE_LABEL[data.style ?? 'investor']}
          </div>
          <div>
            <Term id="coverage">Data coverage</Term>
          </div>
          <div className="font-medium text-muted">{fmtNum(data.coverage * 100)}%</div>
        </div>
      </div>

      {/* Category breakdown */}
      <div className="space-y-1.5">
        {data.categories.map((c) => (
          <div key={c.name} className="flex items-center gap-3 text-xs">
            <span className="w-36 shrink-0 whitespace-nowrap text-muted">
              {categoryEntry(c.name) ? (
                <Term id={categoryEntry(c.name) ?? 'score'}>{c.name}</Term>
              ) : (
                c.name
              )}
              <span className="ml-1 text-2xs text-subtle">{fmtNum(c.weight * 100)}%</span>
            </span>
            <div className="h-2 flex-1 overflow-hidden rounded-xs bg-panelalt">
              <div
                className={`h-full rounded-xs ${barTone(c.score ?? 50)}`}
                style={{ width: `${c.score ?? 0}%` }}
              />
            </div>
            <span className="w-8 text-right font-medium text-ink">
              {c.score != null ? fmtNum(c.score) : '—'}
            </span>
          </div>
        ))}
      </div>

      {/* Reasons */}
      {data.reasons.length > 0 && (
        <div>
          <div className="mb-1 text-2xs font-medium text-muted">Drivers</div>
          <ul className="space-y-0.5 text-xs text-muted">
            {data.reasons.map((r) => (
              <li key={r} className="flex items-center gap-1.5">
                <span className="text-subtle">•</span>
                {r}
              </li>
            ))}
          </ul>
        </div>
      )}

      <TrackRecord current={data.rating} />

      {/* Disclaimer */}
      <p className="flex items-start gap-1.5 text-2xs text-subtle">
        <Info size={12} className="mt-0.5 shrink-0" />
        {data.disclaimer}
      </p>
    </div>
  )
}
