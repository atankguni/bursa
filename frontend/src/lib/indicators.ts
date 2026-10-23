// Chart indicators computed from price points (pure: no chart, no DOM).
import type { LineData, UTCTimestamp } from 'lightweight-charts'
import type { PricePoint } from '../api'
import { parseServerTime } from './format'

/** A server timestamp as the chart's time (seconds, UTC). */
export const toTime = (iso: string): UTCTimestamp =>
  // UTCTimestamp is a branded number: a cast is the only way to make one.
  // oxlint-disable-next-line typescript/no-unsafe-type-assertion
  Math.floor((parseServerTime(iso)?.getTime() ?? 0) / 1000) as UTCTimestamp

/** Simple moving average of the close; starts once `period` points exist. */
export function sma(points: PricePoint[], period: number): LineData[] {
  const out: LineData[] = []
  let sum = 0
  points.forEach((p, i) => {
    sum += p.close
    const dropped = points[i - period]
    if (dropped) sum -= dropped.close
    if (i >= period - 1) out.push({ time: toTime(p.timestamp), value: sum / period })
  })
  return out
}

/** Wilder's RSI: the first `period` changes are averaged, later ones smoothed. */
export function rsi(points: PricePoint[], period = 14): LineData[] {
  const out: LineData[] = []
  let avgGain = 0
  let avgLoss = 0
  points.forEach((p, i) => {
    const prev = points[i - 1]
    if (!prev) return
    const d = p.close - prev.close
    const gain = Math.max(d, 0)
    const loss = Math.max(-d, 0)
    if (i <= period) {
      avgGain += gain / period
      avgLoss += loss / period
      if (i < period) return
    } else {
      avgGain = (avgGain * (period - 1) + gain) / period
      avgLoss = (avgLoss * (period - 1) + loss) / period
    }
    const value = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss)
    out.push({ time: toTime(p.timestamp), value })
  })
  return out
}
