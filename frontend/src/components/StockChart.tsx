import { useEffect, useRef } from 'react'
import {
  ColorType,
  CrosshairMode,
  LineStyle,
  PriceScaleMode,
  createChart,
  type CandlestickData,
  type HistogramData,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type UTCTimestamp,
} from 'lightweight-charts'
import type { PricePoint } from '../api'
import { readCssColor, useSettings } from '../lib/settings'
import { rsi, sma, toTime } from '../lib/indicators'

export interface Indicators {
  ma20: boolean
  ma50: boolean
  ma200: boolean
  volume: boolean
  rsi: boolean
}

// Soft (default) and high-contrast palettes, per theme. Line series (price in
// line mode, RSI) use the user's accent colour, read from CSS (readCssColor).
const SOFT = {
  dark: {
    background: '#0f172a',
    text: '#cbd5e1',
    grid: '#1e293b',
    border: '#334155',
    bull: '#22c55e',
    bear: '#ef4444',
  },
  light: {
    background: '#ffffff',
    text: '#475569',
    grid: '#e2e8f0',
    border: '#e2e8f0',
    bull: '#16a34a',
    bear: '#dc2626',
  },
} as const

const HIGH = {
  dark: {
    background: '#0f172a',
    text: '#cbd5e1',
    grid: '#334155',
    border: '#475569',
    bull: '#4ade80',
    bear: '#f87171',
  },
  light: {
    background: '#ffffff',
    text: '#334155',
    grid: '#cbd5e1',
    border: '#94a3b8',
    bull: '#15803d',
    bear: '#b91c1c',
  },
} as const

// Hues kept clear of every accent option (blue, indigo, violet, graphite) and of
// the bull/bear candles, so moving averages never look like the price line.
const MA_COLORS = { ma20: '#f59e0b', ma50: '#ec4899', ma200: '#06b6d4' }

export default function StockChart({
  data,
  chartType,
  height = 400,
  indicators,
  visibleFrom,
  compare,
  markers,
}: {
  data: PricePoint[]
  chartType: 'candle' | 'line'
  height?: number
  indicators?: Indicators
  /** ISO date: start the view here (older data stays scrollable). Omit to fit all. */
  visibleFrom?: string | undefined
  /**
   * Overlay a benchmark (e.g. IHSG). The price scale switches to % change from
   * the first visible bar, so both lines start at 0% and rebase as you scroll.
   */
  compare?: { label: string; points: PricePoint[] } | undefined
  /** Event markers (e.g. stock splits), snapped to the first bar on/after `date`. */
  markers?: { date: string; text: string }[] | undefined
}) {
  const mainRef = useRef<HTMLDivElement>(null)
  const rsiRef = useRef<HTMLDivElement>(null)
  const { settings, resolvedTheme } = useSettings()
  const ind = indicators

  useEffect(() => {
    const el = mainRef.current
    if (!el) return
    const c = (settings.highContrast ? HIGH : SOFT)[resolvedTheme]
    const accent = readCssColor('--c-accent')

    const chart = createChart(el, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: c.background },
        textColor: c.text,
      },
      grid: { vertLines: { color: c.grid }, horzLines: { color: c.grid } },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: c.border },
      timeScale: { borderColor: c.border, timeVisible: true, secondsVisible: false },
    })

    let main: ISeriesApi<'Candlestick'> | ISeriesApi<'Line'>
    if (chartType === 'candle') {
      const series = chart.addCandlestickSeries({
        upColor: c.bull,
        downColor: c.bear,
        borderUpColor: c.bull,
        borderDownColor: c.bear,
        wickUpColor: c.bull,
        wickDownColor: c.bear,
      })
      const bars: CandlestickData[] = data.map((p) => ({
        time: toTime(p.timestamp),
        open: p.open,
        high: p.high,
        low: p.low,
        close: p.close,
      }))
      series.setData(bars)
      main = series
    } else {
      const series = chart.addLineSeries({ color: accent, lineWidth: 2 })
      const pts: LineData[] = data.map((p) => ({
        time: toTime(p.timestamp),
        value: p.close,
      }))
      series.setData(pts)
      main = series
    }

    // Snap each marker to the first bar on/after its date (markers need a bar time).
    if (markers?.length && data.length) {
      const times = data.map((p) => toTime(p.timestamp))
      const placed = markers
        .map((m) => {
          const at = toTime(m.date)
          const t = times.find((x) => x >= at)
          return t == null ? null : { time: t, text: m.text }
        })
        .filter((m): m is { time: UTCTimestamp; text: string } => m != null)
        .sort((a, b) => a.time - b.time)
      main.setMarkers(
        placed.map((m) => ({
          time: m.time,
          position: 'aboveBar' as const,
          shape: 'arrowDown' as const,
          color: resolvedTheme === 'dark' ? '#fbbf24' : '#b45309',
          text: m.text,
        })),
      )
    }

    if (ind?.volume) {
      const vol = chart.addHistogramSeries({
        priceFormat: { type: 'volume' },
        priceScaleId: 'vol',
      })
      chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })
      const bars: HistogramData[] = data.map((p) => ({
        time: toTime(p.timestamp),
        value: p.volume,
        color: p.close >= p.open ? `${c.bull}66` : `${c.bear}66`,
      }))
      vol.setData(bars)
    }

    if (compare && compare.points.length > 1) {
      chart.priceScale('right').applyOptions({ mode: PriceScaleMode.Percentage })
      const bench = chart.addLineSeries({
        color: resolvedTheme === 'dark' ? '#cbd5e1' : '#475569',
        lineWidth: 2,
        lineStyle: LineStyle.Dashed,
        title: compare.label,
        priceLineVisible: false,
      })
      bench.setData(
        compare.points.map((p) => ({ time: toTime(p.timestamp), value: p.close })),
      )
    }

    if (ind?.ma20 || ind?.ma50 || ind?.ma200) {
      const add = (period: number, color: string) => {
        const s = chart.addLineSeries({
          color,
          lineWidth: 1,
          priceLineVisible: false,
          lastValueVisible: false,
        })
        s.setData(sma(data, period))
      }
      if (ind.ma20) add(20, MA_COLORS.ma20)
      if (ind.ma50) add(50, MA_COLORS.ma50)
      if (ind.ma200) add(200, MA_COLORS.ma200)
    }

    // Show the requested span; the rest of the series stays loaded so moving
    // averages are correct from the first visible bar and the user can scroll back.
    const fromTs = visibleFrom ? toTime(visibleFrom) : null
    const [first, newest] = [data[0], data[data.length - 1]]
    const showSpan = (target: IChartApi) =>
      fromTs != null && first && newest && fromTs > toTime(first.timestamp)
        ? target
            .timeScale()
            .setVisibleRange({ from: fromTs, to: toTime(newest.timestamp) })
        : target.timeScale().fitContent()
    showSpan(chart)

    const observer = new ResizeObserver((entries) => {
      const e = entries[0]
      if (e) chart.applyOptions({ width: e.contentRect.width })
    })
    observer.observe(el)

    // Optional RSI pane (separate chart below).
    let rsiChart: IChartApi | null = null
    if (ind?.rsi && rsiRef.current) {
      const rc = (settings.highContrast ? HIGH : SOFT)[resolvedTheme]
      rsiChart = createChart(rsiRef.current, {
        height: 120,
        layout: {
          background: { type: ColorType.Solid, color: rc.background },
          textColor: rc.text,
        },
        grid: { vertLines: { color: rc.grid }, horzLines: { color: rc.grid } },
        rightPriceScale: { borderColor: rc.border },
        timeScale: { borderColor: rc.border, timeVisible: true, secondsVisible: false },
      })
      const rsiSeries = rsiChart.addLineSeries({ color: accent, lineWidth: 1 })
      rsiSeries.setData(rsi(data, 14))
      const guide = {
        color: rc.border,
        lineStyle: LineStyle.Dashed,
        lineWidth: 1,
        axisLabelVisible: false,
        title: '',
      } as const
      rsiSeries.createPriceLine({ ...guide, price: 70 })
      rsiSeries.createPriceLine({ ...guide, price: 30 })
      showSpan(rsiChart)
      const rObs = new ResizeObserver((entries) => {
        const e = entries[0]
        if (e && rsiChart) rsiChart.applyOptions({ width: e.contentRect.width })
      })
      rObs.observe(rsiRef.current)
      return () => {
        rObs.disconnect()
        observer.disconnect()
        rsiChart?.remove()
        chart.remove()
      }
    }

    return () => {
      observer.disconnect()
      chart.remove()
    }
  }, [
    data,
    chartType,
    height,
    resolvedTheme,
    settings.highContrast,
    settings.accent,
    ind?.ma20,
    ind?.ma50,
    ind?.ma200,
    ind?.volume,
    ind?.rsi,
    visibleFrom,
    compare,
    markers,
  ])

  const last = data[data.length - 1]?.close ?? null
  const label =
    (last != null
      ? `Price chart with ${data.length} points; latest close ${last}`
      : 'Price chart') + (compare ? `, compared with ${compare.label} in % change` : '')

  return (
    <div className="w-full" role="img" aria-label={label}>
      <div ref={mainRef} className="w-full" />
      {ind?.rsi && <div ref={rsiRef} className="mt-1 w-full" />}
    </div>
  )
}
