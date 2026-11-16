/** The stock modal's chart tab: span, chart type, indicators, IHSG overlay. */
import { lazy, Suspense, useMemo, useState } from 'react'
import { CandlestickChart, LineChart } from 'lucide-react'
import { type ChartSpan } from '../../api'
import { useHistory, useIndexHistory } from '../../hooks'
import { useSettings } from '../../lib/settings'
import { SPANS, spanStart } from '../../lib/spans'
import { isBool, isFlags, useStoredState } from '../../lib/storedState'
import type { Indicators } from '../StockChart'
import IndicatorMenu from './IndicatorMenu'

// lightweight-charts is heavy; load it only when a chart is actually shown.
const StockChart = lazy(() => import('../StockChart'))

/** Classes for one button of a segmented control. */
const seg = (active: boolean) => `segment ${active ? 'active' : ''}`

const isSpan = (v: unknown): v is ChartSpan => SPANS.some((s) => s.value === v)
const DEFAULT_IND: Indicators = {
  ma20: false,
  ma50: false,
  ma200: false,
  volume: true,
  rsi: false,
}
const isInd = isFlags<keyof Indicators>(['ma20', 'ma50', 'ma200', 'volume', 'rsi'])

/**
 * The chart's options. Kept by the modal, so they survive switching tabs. Type and
 * range start from Settings → Display each time; span, indicators and the IHSG
 * overlay are remembered across stocks and visits.
 */
export function useChartOptions() {
  const { settings } = useSettings()
  const [range, setRange] = useState<'1d' | '1m'>(settings.chartRange)
  const [span, setSpan] = useStoredState<ChartSpan>('chart.span', '1y', isSpan)
  const [chartType, setChartType] = useState<'candle' | 'line'>(settings.chartType)
  const [ind, setInd] = useStoredState<Indicators>('chart.indicators', DEFAULT_IND, isInd)
  // Benchmark overlay: IHSG daily bars for the same span (daily view only).
  const [vsIhsg, setVsIhsg] = useStoredState('chart.vsIhsg', false, isBool)
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

  const skeleton = (
    <div
      className="skeleton min-h-0 flex-1"
      aria-busy="true"
      aria-label="Loading chart…"
    />
  )

  return (
    // Fills the tab: controls on top, the chart takes the rest (at least 340px).
    <div className="flex min-h-[340px] flex-1 flex-col">
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <div className="segmented">
          {(['1d', '1m'] as const).map((i) => (
            <button key={i} onClick={() => setRange(i)} className={seg(range === i)}>
              {i === '1d' ? 'Daily' : '1-Min'}
            </button>
          ))}
        </div>
        {range === '1d' && (
          <div className="segmented" role="group" aria-label="Time span">
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
        <div className="segmented" role="group" aria-label="Chart type">
          <button
            onClick={() => setChartType('line')}
            aria-pressed={chartType === 'line'}
            aria-label="Line"
            title="Line"
            className={`flex items-center gap-1 ${seg(chartType === 'line')}`}
          >
            <LineChart size={13} aria-hidden />
            <span className="hidden sm:inline">Line</span>
          </button>
          <button
            onClick={() => setChartType('candle')}
            aria-pressed={chartType === 'candle'}
            aria-label="Candles"
            title="Candles"
            className={`flex items-center gap-1 ${seg(chartType === 'candle')}`}
          >
            <CandlestickChart size={13} aria-hidden />
            <span className="hidden sm:inline">Candle</span>
          </button>
        </div>
        <IndicatorMenu
          ind={ind}
          setInd={setInd}
          vsIhsg={range === '1d' ? vsIhsg : undefined}
          setVsIhsg={range === '1d' ? setVsIhsg : undefined}
        />
        {history.isFetching && !history.isLoading && (
          <span className="text-2xs text-subtle" aria-live="polite">
            {span === '5y' || span === 'max'
              ? 'Loading full price history (the first time takes a few seconds)…'
              : 'Updating…'}
          </span>
        )}
      </div>

      <div className="mt-3 flex min-h-0 flex-1 flex-col">
        {history.isLoading ? (
          skeleton
        ) : history.data && history.data.points.length > 0 ? (
          <Suspense fallback={skeleton}>
            <StockChart
              fill
              intraday={range === '1m'}
              data={history.data.points}
              chartType={chartType}
              indicators={ind}
              visibleFrom={visibleFrom}
              compare={compare}
              markers={splitMarkers}
            />
          </Suspense>
        ) : (
          <div className="flex flex-1 items-center justify-center text-muted">
            No price data yet for this interval.
          </div>
        )}
      </div>
    </div>
  )
}
