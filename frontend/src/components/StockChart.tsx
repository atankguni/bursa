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

export default function StockChart({ data, chartType, height = 420 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    // Build a fresh chart for the current series type.
    const chart = createChart(container, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: '#0f172a' },
        textColor: '#cbd5e1',
      },
      grid: {
        vertLines: { color: '#1e293b' },
        horzLines: { color: '#1e293b' },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: '#334155' },
      timeScale: { borderColor: '#334155', timeVisible: true, secondsVisible: false },
    })
    chartRef.current = chart

    if (chartType === 'candle') {
      const series = chart.addCandlestickSeries({
        upColor: '#16a34a',
        downColor: '#dc2626',
        borderUpColor: '#16a34a',
        borderDownColor: '#dc2626',
        wickUpColor: '#16a34a',
        wickDownColor: '#dc2626',
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
      const series = chart.addLineSeries({
        color: '#38bdf8',
        lineWidth: 2,
      })
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
      if (entry) {
        chart.applyOptions({ width: entry.contentRect.width })
      }
    })
    observer.observe(container)

    return () => {
      observer.disconnect()
      chart.remove()
      chartRef.current = null
    }
  }, [data, chartType, height])

  return <div ref={containerRef} className="w-full" />
}
