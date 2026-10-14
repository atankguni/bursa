import { useEffect, useRef } from 'react'
import { ColorType, createChart, type AreaData, type IChartApi } from 'lightweight-charts'
import type { EquityPoint } from '../api'
import { useSettings } from '../lib/settings'

const PALETTE = {
  dark: { background: '#0f172a', text: '#cbd5e1', grid: '#1e293b', line: '#22c55e' },
  light: { background: '#ffffff', text: '#475569', grid: '#e2e8f0', line: '#16a34a' },
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

  return <div ref={ref} className="w-full" />
}
