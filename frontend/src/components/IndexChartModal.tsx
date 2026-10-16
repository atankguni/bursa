import { lazy, Suspense, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import type { ChartSpan, MarketIndex } from '../api'
import { useIndexHistory } from '../hooks'
import { fmtPct, fmtPrice } from '../lib/format'
import { useSettings } from '../lib/settings'
import { SPANS, spanStart } from '../lib/spans'

const StockChart = lazy(() => import('./StockChart'))

/** Chart for one IDX index. IHSG/LQ45/JII have decades of history; others build up daily. */
export default function IndexChartModal({
  index,
  onClose,
}: {
  index: MarketIndex
  onClose: () => void
}) {
  const [span, setSpan] = useState<ChartSpan>('1y')
  const { settings } = useSettings()
  const history = useIndexHistory(index.code, span)
  const points = history.data?.points ?? []

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const pct = index.change_percent
  const tone =
    !settings.colorizeChanges || pct == null || pct === 0
      ? 'text-muted'
      : pct > 0
        ? 'text-bull'
        : 'text-bear'
  const seg = (active: boolean) =>
    `px-2.5 py-1 text-xs transition ${active ? 'bg-active text-ink' : 'text-muted hover:text-ink'}`

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-label={`${index.name} chart`}
        className="flex w-full max-w-3xl animate-fade-in flex-col rounded-md bg-panel p-5 shadow-pop ring-1 ring-line"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold">
                {index.code === 'COMPOSITE' ? 'IHSG' : index.code}
              </h2>
              <span className="rounded-sm bg-panelalt px-1.5 py-0.5 text-[10px] text-muted">
                {index.group}
              </span>
            </div>
            <p className="text-xs text-muted">{index.name}</p>
            <div className="mt-1.5 flex items-baseline gap-3">
              <span className="text-xl font-bold tabular-nums">
                {fmtPrice(index.last)}
              </span>
              {pct != null && (
                <span className={`text-xs font-medium tabular-nums ${tone}`}>
                  {index.change != null &&
                    `${index.change > 0 ? '+' : ''}${fmtPrice(index.change)} `}
                  ({fmtPct(pct)})
                </span>
              )}
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded p-1.5 text-muted transition hover:bg-panelalt hover:text-ink"
          >
            <X size={18} />
          </button>
        </div>

        {index.has_history && (
          <div
            className="mt-3 flex w-fit overflow-hidden rounded ring-1 ring-line-strong"
            role="group"
            aria-label="Time span"
          >
            {SPANS.map((s) => (
              <button
                key={s.value}
                onClick={() => setSpan(s.value)}
                aria-pressed={span === s.value}
                className={seg(span === s.value)}
              >
                {s.label}
              </button>
            ))}
          </div>
        )}

        <div className="mt-3">
          {history.isFetching && !history.isLoading && (
            <p className="mb-1 text-[11px] text-subtle" aria-live="polite">
              Updating…
            </p>
          )}
          {history.isLoading ? (
            <div className="flex h-[360px] items-center justify-center text-sm text-muted">
              Loading chart…
            </div>
          ) : points.length >= 2 ? (
            <Suspense
              fallback={
                <div className="flex h-[360px] items-center justify-center text-sm text-muted">
                  Loading chart…
                </div>
              }
            >
              <StockChart
                data={points}
                chartType="line"
                height={360}
                indicators={{
                  ma20: false,
                  ma50: false,
                  ma200: false,
                  volume: false,
                  rsi: false,
                }}
                visibleFrom={index.has_history ? spanStart(span) : undefined}
              />
            </Suspense>
          ) : (
            <div className="flex h-[200px] flex-col items-center justify-center gap-1 px-6 text-center text-xs text-muted">
              <span>No price history for {index.name} yet.</span>
              <span className="text-[11px] text-subtle">
                The data provider only gives today’s value for this index, so Bursa saves
                each day’s close and the chart builds up from
                {index.history_since ? ` ${index.history_since}` : ' today'}.
              </span>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body,
  )
}
