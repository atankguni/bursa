import { lazy, Suspense, useState } from 'react'
import type { ChartSpan, MarketIndex } from '../api'
import { useIndexHistory } from '../hooks'
import { fmtPct, fmtPrice } from '../lib/format'
import { useSettings } from '../lib/settings'
import { SPANS, spanStart } from '../lib/spans'
import Modal from './Modal'

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

  const pct = index.change_percent
  const tone =
    !settings.colorizeChanges || pct == null || pct === 0
      ? 'text-muted'
      : pct > 0
        ? 'text-bull'
        : 'text-bear'
  const seg = (active: boolean) =>
    `px-2.5 py-1 text-xs transition ${active ? 'bg-active text-ink' : 'text-muted hover:text-ink'}`

  return (
    <Modal
      label={`${index.name} chart`}
      onClose={onClose}
      header={
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
            <span className="text-xl font-bold tabular-nums">{fmtPrice(index.last)}</span>
            {pct != null && (
              <span className={`text-xs font-medium tabular-nums ${tone}`}>
                {index.change != null &&
                  `${index.change > 0 ? '+' : ''}${fmtPrice(index.change)} `}
                ({fmtPct(pct)})
              </span>
            )}
          </div>
        </div>
      }
    >
      {index.has_history && (
        <div
          className="flex w-fit overflow-hidden rounded ring-1 ring-line-strong"
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
    </Modal>
  )
}
