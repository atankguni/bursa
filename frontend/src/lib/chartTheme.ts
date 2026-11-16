/**
 * One look for every chart, read from the theme tokens in index.css (so light,
 * dark, high contrast and the accent all follow): no vertical grid, faint
 * horizontal lines, borderless axes, Inter labels. Call inside the chart effect
 * (the theme attributes are set in layout effects, before it runs).
 */
import {
  ColorType,
  LineStyle,
  type DeepPartial,
  type ChartOptions,
} from 'lightweight-charts'
import { readCssColor } from './settings'

export interface ChartColors {
  background: string
  text: string
  grid: string
  border: string
  bull: string
  bear: string
  accent: string
  neutral: string
}

export function chartColors(): ChartColors {
  return {
    background: readCssColor('--c-panel', '#ffffff'),
    text: readCssColor('--c-muted', '#5f5f6a'),
    grid: readCssColor('--c-line', '#ececf0'),
    border: readCssColor('--c-line-strong', '#dadae0'),
    bull: readCssColor('--c-bull', '#059669'),
    bear: readCssColor('--c-bear', '#e11d48'),
    accent: readCssColor('--c-accent'),
    neutral: readCssColor('--c-subtle', '#83838f'),
  }
}

export function baseChartOptions(c: ChartColors): DeepPartial<ChartOptions> {
  const font = getComputedStyle(document.body).fontFamily
  const cross = {
    color: c.neutral,
    width: 1 as const,
    style: LineStyle.Dashed,
    labelBackgroundColor: c.text,
  }
  return {
    layout: {
      background: { type: ColorType.Solid, color: c.background },
      textColor: c.text,
      fontFamily: font,
      fontSize: 11,
      // The footer's "Charts by TradingView" link on every page is the
      // attribution the library's licence asks for, so the in-chart logo can go.
      attributionLogo: false,
      // The line between price and an indicator pane (RSI); drag it to resize.
      panes: { separatorColor: c.grid, separatorHoverColor: c.border },
    },
    grid: { vertLines: { visible: false }, horzLines: { color: c.grid } },
    rightPriceScale: { borderVisible: false },
    timeScale: { borderVisible: false },
    crosshair: { vertLine: cross, horzLine: cross },
  }
}

/** Axis labels for rupiah amounts: 24.2M, 1.35B, 950K. */
export function compactAmount(v: number): string {
  const a = Math.abs(v)
  if (a >= 1e12) return `${(v / 1e12).toFixed(2)}T`
  if (a >= 1e9) return `${(v / 1e9).toFixed(2)}B`
  if (a >= 1e6) return `${(v / 1e6).toFixed(1)}M`
  if (a >= 1e3) return `${(v / 1e3).toFixed(0)}K`
  return v.toFixed(0)
}
