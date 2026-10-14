import { useEffect, useRef } from 'react'
import { ColorType, createChart, type AreaData, type IChartApi } from 'lightweight-charts'
import type { EquityPoint } from '../api'
import { useSettings } from '../lib/settings'

const PALETTE = {
  dark: { background: '#0f172a', text: '#cbd5e1', grid: '#334155', line: '#4ade80' },
  light: { background: '#ffffff', text: '#334155', grid: '#cbd5e1', line: '#15803d' },
} as const

/** Portfolio value over time (area series). */
export default function PortfolioChart({
  data,
  height = 260,
}: {
  data: EquityPoint[]
  height?: number
}) {
  const ref = useRef<HTMLDivElement>(null)
  const { resolvedTheme } = useSettings()

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const c = PALETTE[resolvedTheme]

    const chart: IChartApi = createChart(el, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: c.background },
        textColor: c.text,
      },
      grid: { vertLines: { color: c.grid }, horzLines: { color: c.grid } },
      rightPriceScale: { borderColor: c.grid },
      timeScale: { borderColor: c.grid },
    })
    const series = chart.addAreaSeries({
      lineColor: c.line,
      topColor: `${c.line}55`,
      bottomColor: `${c.line}05`,
      lineWidth: 2,
    })
    series.setData(data.map((p) => ({ time: p.date, value: p.value }) as AreaData))
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
  }, [data, height, resolvedTheme])

  const last = data.length > 0 ? data[data.length - 1].value : null
  return (
    <div
      ref={ref}
      className="w-full"
      role="img"
      aria-label={
        last != null
          ? `Portfolio value chart over ${data.length} days; latest ${last}`
          : 'Portfolio value chart'
      }
    />
  )
}
