/** The stock modal's chart tab: span, chart type, indicators, IHSG overlay. */
import { lazy, Suspense, useMemo, useState } from 'react'
import { CandlestickChart, LineChart } from 'lucide-react'
import { type ChartSpan } from '../../api'
import { useHistory, useIndexHistory } from '../../hooks'
import { useSettings } from '../../lib/settings'
import { SPANS, spanStart } from '../../lib/spans'

// lightweight-charts is heavy; load it only when a chart is actually shown.
import type { Indicators } from '../StockChart'
const StockChart = lazy(() => import('../StockChart'))

/** Classes for one button of a segmented control. */
const seg = (active: boolean) =>
  `px-2.5 py-1 text-xs transition ${active ? 'bg-active text-ink' : 'text-muted hover:text-ink'}`

/** The chart's options. Kept by the modal, so they survive switching tabs. */
export function useChartOptions() {
  const { settings } = useSettings()
  const [range, setRange] = useState<'1d' | '1m'>(settings.chartRange)
  const [span, setSpan] = useState<ChartSpan>('1y')
  const [chartType, setChartType] = useState<'candle' | 'line'>(settings.chartType)
  const [ind, setInd] = useState<Indicators>({
    ma20: false,
    ma50: false,
    ma200: false,
    volume: true,
    rsi: false,
  })
  // Benchmark overlay: IHSG daily bars for the same span (daily view only).
  const [vsIhsg, setVsIhsg] = useState(false)
  return {
    range,
    setRange,
    span,
    setSpan,
    chartType,
    setChartType,
    ind,
    setInd,
    vsIhsg,
    setVsIhsg,
  }
}

export type ChartOptions = ReturnType<typeof useChartOptions>

export default function ChartTab({
  ticker,
  options,
}: {
  ticker: string
  options: ChartOptions
}) {
  const { range, setRange, span, setSpan, chartType, setChartType, ind, setInd } = options
  const { vsIhsg, setVsIhsg } = options
  const history = useHistory(ticker, range, span, true)
  const ihsg = useIndexHistory('COMPOSITE', span, vsIhsg && range === '1d')
  const splitMarkers = useMemo(
    () =>
      range === '1d'
        ? (history.data?.splits ?? []).map((s) => ({
            date: s.ex_date,
            text: `Split ${s.ratio >= 1 ? `${s.ratio}:1` : `1:${Math.round(1 / s.ratio)}`}`,
          }))
        : undefined,
    [range, history.data?.splits],
  )
  const compare = useMemo(
    () =>
      vsIhsg && range === '1d' && ihsg.data
        ? { label: 'IHSG', points: ihsg.data.points }
        : undefined,
    [vsIhsg, range, ihsg.data],
  )
  const visibleFrom = range === '1d' ? spanStart(span) : undefined

  return (
    <>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <div className="flex overflow-hidden rounded ring-1 ring-line-strong">
          {(['1d', '1m'] as const).map((i) => (
            <button key={i} onClick={() => setRange(i)} className={seg(range === i)}>
              {i === '1d' ? 'Daily' : '1-Min'}
            </button>
          ))}
        </div>
        {range === '1d' && (
          <div
            className="flex overflow-hidden rounded ring-1 ring-line-strong"
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
        <div className="flex overflow-hidden rounded ring-1 ring-line-strong">
          <button
            onClick={() => setChartType('line')}
            className={`flex items-center gap-1 ${seg(chartType === 'line')}`}
          >
            <LineChart size={13} /> Line
          </button>
          <button
            onClick={() => setChartType('candle')}
            className={`flex items-center gap-1 ${seg(chartType === 'candle')}`}
          >
            <CandlestickChart size={13} /> Candle
          </button>
        </div>
        <div className="flex flex-wrap gap-1">
          {(
            [
              ['ma20', 'MA20'],
              ['ma50', 'MA50'],
              ['ma200', 'MA200'],
              ['volume', 'Vol'],
              ['rsi', 'RSI'],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setInd((s) => ({ ...s, [key]: !s[key] }))}
              className={`rounded px-2 py-1 text-[11px] font-medium ring-1 transition ${
                ind[key]
                  ? 'bg-accent/15 text-accent ring-accent/30'
                  : 'text-muted ring-line-strong hover:bg-panelalt hover:text-ink'
              }`}
            >
              {label}
            </button>
          ))}
          {range === '1d' && (
            <button
              onClick={() => setVsIhsg((v) => !v)}
              aria-pressed={vsIhsg}
              title="Compare with IHSG: both lines in % change from the left edge of the chart"
              className={`rounded px-2 py-1 text-[11px] font-medium ring-1 transition ${
                vsIhsg
                  ? 'bg-accent/15 text-accent ring-accent/30'
                  : 'text-muted ring-line-strong hover:bg-panelalt hover:text-ink'
              }`}
            >
              vs IHSG
            </button>
          )}
        </div>
      </div>

      <div className="mt-3">
        {history.isFetching && !history.isLoading && (
          <p className="mb-1 text-[11px] text-subtle" aria-live="polite">
            {span === '5y' || span === 'max'
              ? 'Loading full price history (first time can take a few seconds)…'
              : 'Updating…'}
          </p>
        )}
        {history.isLoading ? (
          <div className="flex h-[400px] items-center justify-center text-muted">
            Loading chart…
          </div>
        ) : history.data && history.data.points.length > 0 ? (
          <Suspense
            fallback={
              <div className="flex h-[400px] items-center justify-center text-muted">
                Loading chart…
              </div>
            }
          >
            <StockChart
              data={history.data.points}
              chartType={chartType}
              indicators={ind}
              visibleFrom={visibleFrom}
              compare={compare}
              markers={splitMarkers}
            />
          </Suspense>
        ) : (
          <div className="flex h-[400px] items-center justify-center text-muted">
            No price data yet for this interval.
          </div>
        )}
      </div>
    </>
  )
}
