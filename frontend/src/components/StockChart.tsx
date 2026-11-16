import { useEffect, useMemo, useRef, useState } from 'react'
import {
  CandlestickSeries,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  LineStyle,
  PriceScaleMode,
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type MouseEventParams,
  type IRange,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts'
import type { PricePoint } from '../api'
import { baseChartOptions, chartColors } from '../lib/chartTheme'
import { fmtDay, fmtNum, fmtPct, fmtVolume, parseServerTime } from '../lib/format'
import { useSettings } from '../lib/settings'
import { rsi, sma, toTime } from '../lib/indicators'

export interface Indicators {
  ma20: boolean
  ma50: boolean
  ma200: boolean
  volume: boolean
  rsi: boolean
}

const NO_INDICATORS: Indicators = {
  ma20: false,
  ma50: false,
  ma200: false,
  volume: false,
  rsi: false,
}

// Colours come from the theme (lib/chartTheme); line series (price in line
// mode, RSI) use the accent. Moving averages keep fixed, distinct hues.
export const MA_COLORS = { ma20: '#f59e0b', ma50: '#ec4899', ma200: '#06b6d4' }
const MAS = [
  ['ma20', 20],
  ['ma50', 50],
  ['ma200', 200],
] as const

// Minute bars are instants, shown in exchange time (WIB).
const minuteFmt = new Intl.DateTimeFormat('en-GB', {
  hour: '2-digit',
  minute: '2-digit',
  timeZone: 'Asia/Jakarta',
})

/** Index of the first time ≥ t (times ascending). */
function lowerBound(times: number[], t: number) {
  let lo = 0
  let hi = times.length
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if ((times[mid] ?? 0) < t) lo = mid + 1
    else hi = mid
  }
  return lo
}

/** % change between the first and last bar inside [from, to]. */
function changeWithin(points: PricePoint[], times: number[], from: number, to: number) {
  const a = points[lowerBound(times, from)]
  const b = points[lowerBound(times, to + 1) - 1]
  if (!a || !b || a === b || a.close === 0) return null
  return { pct: (b.close / a.close - 1) * 100, first: a, last: b }
}

/**
 * Price chart: candles or a line, with optional moving averages, volume, RSI (in
 * its own pane, scrolling with the price), a benchmark overlay and markers.
 * A legend above it reads out the bar under the cursor (or the latest one) and
 * the change across what's on screen.
 *
 * The chart is built once (again only when the theme changes); toggling an
 * indicator adds or removes just that series, so the zoom stays where it is.
 */
export default function StockChart({
  data,
  chartType,
  height = 400,
  fill = false,
  intraday = false,
  indicators,
  visibleFrom,
  compare,
  markers,
  precision = 0,
}: {
  data: PricePoint[]
  chartType: 'candle' | 'line'
  /** Fixed height in px (ignored with `fill`). */
  height?: number
  /** Take the height of the parent (a flex column) instead of `height`. */
  fill?: boolean
  /** Minute bars: the legend shows times. */
  intraday?: boolean
  indicators?: Indicators | undefined
  /** ISO date: start the view here (older data stays scrollable). Omit to fit all. */
  visibleFrom?: string | undefined
  /**
   * Overlay a benchmark (e.g. IHSG). The price scale switches to % change from
   * the first visible bar, so both lines start at 0% and rebase as you scroll.
   */
  compare?: { label: string; points: PricePoint[] } | undefined
  /** Event markers (e.g. stock splits), snapped to the first bar on/after `date`. */
  markers?: { date: string; text: string }[] | undefined
  /** Decimals on the price axis: 0 for IDX stocks (whole rupiah), 2 for indices. */
  precision?: number
}) {
  const boxRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const mainRef = useRef<ISeriesApi<'Candlestick'> | ISeriesApi<'Line'> | null>(null)
  const { settings, resolvedTheme } = useSettings()
  // The chart is rebuilt (and every series re-added) only when its colours change.
  const themeKey = `${resolvedTheme}|${String(settings.highContrast)}|${settings.accent}`
  const ind = indicators ?? NO_INDICATORS

  const times = useMemo(() => data.map((p) => toTime(p.timestamp)), [data])
  const compareTimes = useMemo(
    () => compare?.points.map((p) => toTime(p.timestamp)) ?? [],
    [compare],
  )
  const maLines = useMemo(
    () => ({ ma20: sma(data, 20), ma50: sma(data, 50), ma200: sma(data, 200) }),
    [data],
  )
  const [hoverTime, setHoverTime] = useState<number | null>(null)
  const [shown, setShown] = useState<{ from: number; to: number } | null>(null)

  // The chart itself.
  useEffect(() => {
    const el = boxRef.current
    if (!el) return
    const c = chartColors()
    const base = baseChartOptions(c)
    const chart = createChart(el, {
      ...base,
      autoSize: true,
      crosshair: { ...base.crosshair, mode: CrosshairMode.Normal },
      timeScale: { borderVisible: false, timeVisible: true, secondsVisible: false },
    })
    // Swapping line ⇄ candles empties the price pane for a moment: keep it.
    chart.panes()[0]?.setPreserveEmptyPane(true)
    chartRef.current = chart
    return () => {
      chartRef.current = null
      chart.remove()
    }
  }, [themeKey])

  // Times on the axis only for minute bars (daily bars would all read 00:00).
  useEffect(() => {
    chartRef.current?.applyOptions({ timeScale: { timeVisible: intraday } })
  }, [themeKey, intraday])

  // Legend: follow the crosshair and the visible span.
  useEffect(() => {
    const chart = chartRef.current
    if (!chart) return
    const onMove = (p: MouseEventParams) =>
      setHoverTime(typeof p.time === 'number' ? p.time : null)
    const onRange = (r: IRange<Time> | null) =>
      setShown(
        r && typeof r.from === 'number' && typeof r.to === 'number'
          ? { from: r.from, to: r.to }
          : null,
      )
    chart.subscribeCrosshairMove(onMove)
    chart.timeScale().subscribeVisibleTimeRangeChange(onRange)
    return () => {
      if (chartRef.current !== chart) return
      chart.unsubscribeCrosshairMove(onMove)
      chart.timeScale().unsubscribeVisibleTimeRangeChange(onRange)
    }
  }, [themeKey])

  // Price: candles or a line.
  useEffect(() => {
    const chart = chartRef.current
    if (!chart) return
    const c = chartColors()
    const priceFormat = {
      type: 'price' as const,
      precision,
      minMove: 1 / 10 ** precision,
    }
    let series: ISeriesApi<'Candlestick'> | ISeriesApi<'Line'>
    if (chartType === 'candle') {
      const s = chart.addSeries(CandlestickSeries, {
        priceFormat,
        upColor: c.bull,
        downColor: c.bear,
        borderUpColor: c.bull,
        borderDownColor: c.bear,
        wickUpColor: c.bull,
        wickDownColor: c.bear,
      })
      s.setData(
        data.map((p, i) => ({
          time: times[i] ?? toTime(p.timestamp),
          open: p.open,
          high: p.high,
          low: p.low,
          close: p.close,
        })),
      )
      series = s
    } else {
      const s = chart.addSeries(LineSeries, {
        color: c.accent,
        lineWidth: 2,
        priceFormat,
      })
      s.setData(
        data.map((p, i): LineData => ({
          time: times[i] ?? toTime(p.timestamp),
          value: p.close,
        })),
      )
      series = s
    }
    mainRef.current = series
    return () => {
      mainRef.current = null
      if (chartRef.current === chart) chart.removeSeries(series)
    }
  }, [themeKey, data, times, chartType, precision])

  // Markers (e.g. splits), each on the first bar on/after its date.
  useEffect(() => {
    const series = mainRef.current
    if (!series || !markers?.length) return
    const placed = markers
      .map((m) => {
        const t = times[lowerBound(times, toTime(m.date))]
        return t == null ? null : { time: t, text: m.text }
      })
      .filter((m): m is { time: UTCTimestamp; text: string } => m != null)
      .sort((a, b) => a.time - b.time)
    const plugin = createSeriesMarkers(
      series,
      placed.map((m) => ({
        time: m.time,
        position: 'aboveBar' as const,
        shape: 'arrowDown' as const,
        color: resolvedTheme === 'dark' ? '#fbbf24' : '#b45309',
        text: m.text,
      })),
    )
    return () => {
      if (mainRef.current === series) plugin.detach()
    }
  }, [themeKey, times, chartType, precision, markers, resolvedTheme])

  // Volume: faint bars along the bottom of the price pane.
  useEffect(() => {
    const chart = chartRef.current
    if (!chart || !ind.volume) return
    const c = chartColors()
    const vol = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'vol',
      lastValueVisible: false,
      priceLineVisible: false,
    })
    chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })
    vol.setData(
      data.map((p, i) => ({
        time: times[i] ?? toTime(p.timestamp),
        value: p.volume,
        color: p.close >= p.open ? `${c.bull}66` : `${c.bear}66`,
      })),
    )
    return () => {
      if (chartRef.current === chart) chart.removeSeries(vol)
    }
  }, [themeKey, data, times, ind.volume])

  // Moving averages.
  useEffect(() => {
    const chart = chartRef.current
    if (!chart) return
    const on = { ma20: ind.ma20, ma50: ind.ma50, ma200: ind.ma200 }
    const added = MAS.filter(([key]) => on[key]).map(([key]) => {
      const s = chart.addSeries(LineSeries, {
        color: MA_COLORS[key],
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      })
      s.setData(maLines[key])
      return s
    })
    return () => {
      if (chartRef.current === chart) for (const s of added) chart.removeSeries(s)
    }
  }, [themeKey, maLines, ind.ma20, ind.ma50, ind.ma200])

  // Benchmark overlay, in % change from the first visible bar.
  useEffect(() => {
    const chart = chartRef.current
    if (!chart || !compare || compare.points.length < 2) return
    const c = chartColors()
    chart.priceScale('right').applyOptions({ mode: PriceScaleMode.Percentage })
    const bench = chart.addSeries(LineSeries, {
      color: c.neutral,
      lineWidth: 2,
      lineStyle: LineStyle.Dashed,
      title: compare.label,
      priceLineVisible: false,
    })
    bench.setData(
      compare.points.map((p, i) => ({
        time: compareTimes[i] ?? toTime(p.timestamp),
        value: p.close,
      })),
    )
    return () => {
      if (chartRef.current !== chart) return
      chart.removeSeries(bench)
      chart.priceScale('right').applyOptions({ mode: PriceScaleMode.Normal })
    }
  }, [themeKey, compare, compareTimes])

  // RSI, in a pane of its own below the price (same time axis and crosshair).
  useEffect(() => {
    const chart = chartRef.current
    if (!chart || !ind.rsi) return
    const c = chartColors()
    const series = chart.addSeries(
      LineSeries,
      {
        color: c.accent,
        lineWidth: 1,
        priceLineVisible: false,
        title: 'RSI',
        priceFormat: { type: 'price', precision: 0, minMove: 1 },
      },
      1,
    )
    series.setData(rsi(data, 14))
    // About a quarter of the chart, at least 90px (the separator can be dragged).
    const pane = chart.panes()[1]
    if (pane) pane.setHeight(Math.max(90, Math.round(chart.paneSize(0).height * 0.3)))
    const guide = {
      color: c.border,
      lineStyle: LineStyle.Dashed,
      lineWidth: 1,
      axisLabelVisible: false,
      title: '',
    } as const
    series.createPriceLine({ ...guide, price: 70 })
    series.createPriceLine({ ...guide, price: 30 })
    return () => {
      // The emptied pane goes away by itself.
      if (chartRef.current === chart) chart.removeSeries(series)
    }
  }, [themeKey, data, ind.rsi])

  // Show the requested span; the rest of the series stays loaded so moving
  // averages are correct from the first visible bar and the user can scroll back.
  useEffect(() => {
    const chart = chartRef.current
    const first = times[0]
    const newest = times[times.length - 1]
    if (!chart || first == null || newest == null) return
    const fromTs = visibleFrom ? toTime(visibleFrom) : null
    if (fromTs != null && fromTs > first)
      chart.timeScale().setVisibleRange({ from: fromTs, to: newest })
    else chart.timeScale().fitContent()
  }, [themeKey, times, visibleFrom])

  // --- Legend ---------------------------------------------------------------
  const num = { format: (v: number) => fmtNum(v, precision) }
  // Daily bars are stored at midnight UTC of their trading date.
  const when = (p: PricePoint) => {
    const d = parseServerTime(p.timestamp)
    if (!d) return ''
    return intraday
      ? `${fmtDay(d, { year: false, timeZone: 'Asia/Jakarta' })} ${minuteFmt.format(d)}`
      : fmtDay(d, { timeZone: 'UTC' })
  }
  const tone = (v: number) =>
    !settings.colorizeChanges ? 'text-ink' : v >= 0 ? 'text-bull' : 'text-bear'

  const hoverIdx = hoverTime == null ? -1 : lowerBound(times, hoverTime)
  const idx = hoverIdx >= 0 && times[hoverIdx] === hoverTime ? hoverIdx : data.length - 1
  const bar = data[idx]
  const prev = data[idx - 1]
  const barChange = bar && prev && prev.close ? (bar.close / prev.close - 1) * 100 : null
  const t = times[idx]
  const maNow = MAS.filter(([key]) => ind[key]).map(([key, period]) => ({
    key,
    period,
    value: t == null ? undefined : maLines[key].find((p) => p.time === t)?.value,
  }))
  const span = shown ? changeWithin(data, times, shown.from, shown.to) : null
  const benchSpan =
    shown && compare
      ? changeWithin(compare.points, compareTimes, shown.from, shown.to)
      : null

  const last = data[data.length - 1]?.close ?? null
  const label =
    (last != null
      ? `Price chart with ${data.length} points; latest close ${last}`
      : 'Price chart') + (compare ? `, compared with ${compare.label} in % change` : '')

  return (
    <div className={`flex w-full flex-col ${fill ? 'min-h-0 flex-1' : ''}`}>
      <div className="flex min-h-9 flex-wrap items-baseline justify-between gap-x-4 gap-y-1 pb-2 text-2xs tabular-nums">
        {bar && (
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
            <span className="font-medium text-ink">{when(bar)}</span>
            {(['open', 'high', 'low', 'close'] as const).map((k) => (
              <span key={k} className="text-subtle">
                {k[0]?.toUpperCase()}{' '}
                <span className="text-ink">{num.format(bar[k])}</span>
              </span>
            ))}
            {barChange != null && (
              <span className={`font-medium ${tone(barChange)}`}>
                {fmtPct(barChange)}
              </span>
            )}
            {bar.volume > 0 && (
              <span className="text-subtle">
                Vol <span className="text-ink">{fmtVolume(bar.volume)}</span>
              </span>
            )}
            {maNow.map((m) => (
              <span key={m.key} className="inline-flex items-center gap-1 text-subtle">
                <span
                  className="h-2 w-2 rounded-full"
                  style={{ background: MA_COLORS[m.key] }}
                  aria-hidden
                />
                MA{m.period}{' '}
                <span className="text-ink">
                  {m.value == null ? '—' : num.format(m.value)}
                </span>
              </span>
            ))}
          </div>
        )}
        {span && (
          <div
            className="text-subtle"
            title="Change from the first to the last bar on screen"
          >
            <span className={`font-semibold ${tone(span.pct)}`}>{fmtPct(span.pct)}</span>
            {benchSpan && compare && (
              <>
                {' '}
                vs {compare.label}{' '}
                <span className="font-medium text-ink">{fmtPct(benchSpan.pct)}</span>
              </>
            )}{' '}
            · {when(span.first)} – {when(span.last)}
          </div>
        )}
      </div>
      <div
        ref={boxRef}
        role="img"
        aria-label={label}
        className={`w-full ${fill ? 'min-h-0 flex-1' : ''}`}
        style={fill ? undefined : { height }}
      />
    </div>
  )
}
