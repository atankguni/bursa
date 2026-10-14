import { useEffect, useRef } from 'react'
import {
  ColorType,
  CrosshairMode,
  createChart,
  type CandlestickData,
  type IChartApi,
  type LineData,
  type UTCTimestamp,
} from 'lightweight-charts'
import type { PricePoint } from '../api'
import { useSettings } from '../lib/settings'

interface Props {
  data: PricePoint[]
  chartType: 'candle' | 'line'
  height?: number
}

// Convert the backend's ISO timestamp (naive UTC) into a Unix second value
// that lightweight-charts accepts as a UTCTimestamp.
function toTimestamp(iso: string): UTCTimestamp {
  return Math.floor(new Date(`${iso}Z`).getTime() / 1000) as UTCTimestamp
}

// Chart palette per resolved theme (lightweight-charts needs literal colors).
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

export default function StockChart({ data, chartType, height = 400 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const { resolvedTheme } = useSettings()

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const c = PALETTE[resolvedTheme]

    // Build a fresh chart for the current series type + theme.
    const chart = createChart(container, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: c.background },
        textColor: c.text,
      },
      grid: {
        vertLines: { color: c.grid },
        horzLines: { color: c.grid },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: c.border },
      timeScale: { borderColor: c.border, timeVisible: true, secondsVisible: false },
    })
    chartRef.current = chart

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
        time: toTimestamp(p.timestamp),
        open: p.open,
        high: p.high,
        low: p.low,
        close: p.close,
      }))
      series.setData(bars)
    } else {
      const series = chart.addLineSeries({ color: c.line, lineWidth: 2 })
      const points: LineData[] = data.map((p) => ({
        time: toTimestamp(p.timestamp),
        value: p.close,
      }))
      series.setData(points)
    }

    chart.timeScale().fitContent()

    // Keep the chart sized to its container.
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry) chart.applyOptions({ width: entry.contentRect.width })
    })
    observer.observe(container)

    return () => {
      observer.disconnect()
      chart.remove()
      chartRef.current = null
    }
  }, [data, chartType, height, resolvedTheme])

  return <div ref={containerRef} className="w-full" />
}
