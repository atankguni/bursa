import { useEffect, useRef } from 'react'
import {
  LineStyle,
  createChart,
  type AreaData,
  type IChartApi,
  type LineData,
} from 'lightweight-charts'
import type { EquityPoint } from '../api'
import { baseChartOptions, chartColors, compactAmount } from '../lib/chartTheme'
import { useSettings } from '../lib/settings'

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
      const mine = chart.addLineSeries({
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
      const bench = chart.addLineSeries({
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
      const series = chart.addAreaSeries({
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
  return (
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
  )
}
