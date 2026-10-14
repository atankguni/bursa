import { useEffect, useRef } from 'react'
import {
  ColorType,
  CrosshairMode,
  LineStyle,
  createChart,
  type CandlestickData,
  type HistogramData,
  type IChartApi,
  type LineData,
  type UTCTimestamp,
} from 'lightweight-charts'
import type { PricePoint } from '../api'
import { useSettings } from '../lib/settings'

export interface Indicators {
  ma20: boolean
  ma50: boolean
  ma200: boolean
  volume: boolean
  rsi: boolean
}

const toTime = (iso: string): UTCTimestamp =>
  Math.floor(new Date(`${iso}Z`).getTime() / 1000) as UTCTimestamp

function sma(points: PricePoint[], period: number): LineData[] {
  const out: LineData[] = []
  let sum = 0
  for (let i = 0; i < points.length; i++) {
    sum += points[i].close
    if (i >= period) sum -= points[i - period].close
    if (i >= period - 1) {
      out.push({ time: toTime(points[i].timestamp), value: sum / period })
    }
  }
  return out
}

function rsi(points: PricePoint[], period = 14): LineData[] {
  const out: LineData[] = []
  if (points.length <= period) return out
  let gain = 0
  let loss = 0
  for (let i = 1; i <= period; i++) {
    const d = points[i].close - points[i - 1].close
    if (d >= 0) gain += d
    else loss -= d
  }
  let avgGain = gain / period
  let avgLoss = loss / period
  const push = (i: number) => {
    const rs = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss)
    out.push({ time: toTime(points[i].timestamp), value: rs })
  }
  push(period)
  for (let i = period + 1; i < points.length; i++) {
    const d = points[i].close - points[i - 1].close
    const g = d > 0 ? d : 0
    const l = d < 0 ? -d : 0
    avgGain = (avgGain * (period - 1) + g) / period
    avgLoss = (avgLoss * (period - 1) + l) / period
    push(i)
  }
  return out
}

const PALETTE = {
  dark: {
    background: '#0f172a',
    text: '#cbd5e1',
    grid: '#1e293b',
    border: '#334155',
    bull: '#22c55e',
    bear: '#ef4444',
    line: '#38bdf8',
  },
  light: {
    background: '#ffffff',
    text: '#475569',
    grid: '#e2e8f0',
    border: '#e2e8f0',
    bull: '#16a34a',
    bear: '#dc2626',
    line: '#0284c7',
  },
} as const

const MA_COLORS = { ma20: '#f59e0b', ma50: '#8b5cf6', ma200: '#ec4899' }

export default function StockChart({
  data,
  chartType,
  height = 400,
  indicators,
}: {
  data: PricePoint[]
  chartType: 'candle' | 'line'
  height?: number
  indicators?: Indicators
}) {
  const mainRef = useRef<HTMLDivElement>(null)
  const rsiRef = useRef<HTMLDivElement>(null)
  const { resolvedTheme } = useSettings()
  const ind = indicators

  useEffect(() => {
    const el = mainRef.current
    if (!el) return
    const c = PALETTE[resolvedTheme]

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
    } else {
      const series = chart.addLineSeries({ color: c.line, lineWidth: 2 })
      const pts: LineData[] = data.map((p) => ({
        time: toTime(p.timestamp),
        value: p.close,
      }))
      series.setData(pts)
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

    chart.timeScale().fitContent()

    const observer = new ResizeObserver((entries) => {
      const e = entries[0]
      if (e) chart.applyOptions({ width: e.contentRect.width })
    })
    observer.observe(el)

    // Optional RSI pane (separate chart below).
    let rsiChart: IChartApi | null = null
    if (ind?.rsi && rsiRef.current) {
      const rc = PALETTE[resolvedTheme]
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
      const rsiSeries = rsiChart.addLineSeries({ color: '#a855f7', lineWidth: 1 })
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
      rsiChart.timeScale().fitContent()
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
    ind?.ma20,
    ind?.ma50,
    ind?.ma200,
    ind?.volume,
    ind?.rsi,
  ])

  return (
    <div className="w-full">
      <div ref={mainRef} className="w-full" />
      {ind?.rsi && <div ref={rsiRef} className="mt-1 w-full" />}
    </div>
  )
}
