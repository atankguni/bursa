import { useEffect, useRef, useState } from 'react'
import {
  LineSeries,
  AreaSeries,
  LineStyle,
  createChart,
  type AreaData,
  type IChartApi,
  type LineData,
  type MouseEventParams,
} from 'lightweight-charts'
import type { EquityPoint } from '../api'
import { baseChartOptions, chartColors, compactAmount } from '../lib/chartTheme'
import { fmtMoney, fmtPct } from '../lib/format'
import { useSettings } from '../lib/settings'

const dayFmt = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  timeZone: 'UTC',
})

// The series colour is the user's accent, not bull green: a rising line
// shouldn't look like a price signal.

/**
 * Portfolio value over time (area series). With `hideValues`, the price axis
 * and crosshair labels are turned off so only the shape of the trend shows.
 */
export default function PortfolioChart({
  data,
  height = 260,
  hideValues = false,
  mode = 'value',
}: {
  data: EquityPoint[]
  height?: number
  hideValues?: boolean
  /** 'value' = portfolio value; 'return' = your time-weighted return vs IHSG, in %. */
  mode?: 'value' | 'return'
}) {
  const ref = useRef<HTMLDivElement>(null)
  const { settings, resolvedTheme } = useSettings()
  // The day under the cursor, for the legend (null: the latest day).
  const [hover, setHover] = useState<string | null>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const c = chartColors()
    const accent = c.accent
    const base = baseChartOptions(c)

    const chart: IChartApi = createChart(el, {
      ...base,
      height,
      rightPriceScale: {
        borderVisible: false,
        visible: mode === 'return' || !hideValues,
      },
      crosshair: {
        ...base.crosshair,
        horzLine: {
          ...base.crosshair?.horzLine,
          labelVisible: mode === 'return' || !hideValues,
        },
      },
    })
    if (mode === 'return') {
      // Percentages only (no amounts), so this view is safe in hide-values mode.
      const pct = {
        type: 'custom' as const,
        formatter: (v: number) => `${v.toFixed(1)}%`,
      }
      const mine = chart.addSeries(LineSeries, {
        color: accent,
        lineWidth: 2,
        title: 'You',
        priceFormat: pct,
      })
      mine.setData(
        data.flatMap((p): LineData[] =>
          p.return_pct == null ? [] : [{ time: p.date, value: p.return_pct }],
        ),
      )
      const bench = chart.addSeries(LineSeries, {
        color: c.neutral,
        lineWidth: 2,
        lineStyle: LineStyle.Dashed,
        title: 'IHSG',
        priceFormat: pct,
        priceLineVisible: false,
      })
      bench.setData(
        data.flatMap((p): LineData[] =>
          p.benchmark_pct == null ? [] : [{ time: p.date, value: p.benchmark_pct }],
        ),
      )
    } else {
      const series = chart.addSeries(AreaSeries, {
        lineColor: accent,
        topColor: `${accent}40`,
        bottomColor: `${accent}00`,
        lineWidth: 2,
        priceFormat: { type: 'custom', formatter: compactAmount, minMove: 1 },
        lastValueVisible: !hideValues,
        priceLineVisible: !hideValues,
      })
      series.setData(data.map((p): AreaData => ({ time: p.date, value: p.value })))
    }
    chart.timeScale().fitContent()
    const onMove = (p: MouseEventParams) =>
      setHover(typeof p.time === 'string' ? p.time : null)
    chart.subscribeCrosshairMove(onMove)

    const observer = new ResizeObserver((entries) => {
      const e = entries[0]
      if (e) chart.applyOptions({ width: e.contentRect.width })
    })
    observer.observe(el)
    return () => {
      observer.disconnect()
      chart.remove()
    }
  }, [
    data,
    height,
    hideValues,
    mode,
    resolvedTheme,
    settings.highContrast,
    settings.accent,
  ])

  const last = data[data.length - 1]?.value ?? null
  const point =
    (hover != null ? data.find((p) => p.date === hover) : undefined) ??
    data[data.length - 1]
  const tone = (v: number) =>
    !settings.colorizeChanges ? 'text-ink' : v >= 0 ? 'text-bull' : 'text-bear'
  return (
    <div className="w-full">
      {point && (
        <div className="flex min-h-5 flex-wrap items-baseline gap-x-3 pb-1.5 text-2xs tabular-nums">
          <span className="font-medium text-ink">
            {dayFmt.format(new Date(`${point.date}T00:00:00Z`))}
          </span>
          {mode === 'return' ? (
            <>
              {point.return_pct != null && (
                <span className="text-subtle">
                  You{' '}
                  <span className={`font-medium ${tone(point.return_pct)}`}>
                    {fmtPct(point.return_pct)}
                  </span>
                </span>
              )}
              {point.benchmark_pct != null && (
                <span className="text-subtle">
                  IHSG{' '}
                  <span className="font-medium text-ink">
                    {fmtPct(point.benchmark_pct)}
                  </span>
                </span>
              )}
            </>
          ) : (
            <span className="text-subtle">
              Value{' '}
              <span className="font-medium text-ink">
                {hideValues ? '•••' : `Rp ${fmtMoney(point.value)}`}
              </span>
            </span>
          )}
        </div>
      )}
      <div
        ref={ref}
        className="w-full"
        role="img"
        aria-label={
          last != null && !hideValues
            ? `Portfolio value chart over ${data.length} days; latest ${last}`
            : 'Portfolio value chart'
        }
      />
    </div>
  )
}
