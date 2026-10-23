import { describe, expect, it } from 'vitest'
import type { PricePoint } from '../api'
import { rsi, sma, toTime } from './indicators'

/** One daily point per close, from 2026-01-01. */
const points = (closes: number[]): PricePoint[] =>
  closes.map((close, i) => ({
    timestamp: new Date(Date.UTC(2026, 0, 1 + i)).toISOString().slice(0, 19),
    open: close,
    high: close,
    low: close,
    close,
    volume: 0,
  }))

const values = (rows: { value: number }[]) => rows.map((r) => r.value)

describe('toTime', () => {
  it('turns a server timestamp (UTC) into seconds', () => {
    expect(toTime('2026-01-01T00:00:00')).toBe(Date.UTC(2026, 0, 1) / 1000)
  })
})

describe('sma', () => {
  it('averages the last `period` closes, starting once there are enough', () => {
    const out = sma(points([1, 2, 3, 4, 5]), 3)
    expect(values(out)).toEqual([2, 3, 4])
    expect(out[0]?.time).toBe(toTime('2026-01-03T00:00:00'))
  })

  it('is empty when there are fewer points than the period', () => {
    expect(sma(points([1, 2]), 3)).toEqual([])
  })
})

describe('rsi (Wilder)', () => {
  it('averages the first changes, then smooths', () => {
    // Changes +1, -1, +1 with period 2: first value 50 (gains = losses),
    // then gain 0.75 vs loss 0.25 -> RS 3 -> 75.
    expect(values(rsi(points([1, 2, 1, 2]), 2))).toEqual([50, 75])
  })

  it('smooths with weight (period - 1) / period', () => {
    // Period 3, changes +1 -1 +1 -1. First: gains 2/3, losses 1/3 -> 66.67.
    // Then gains (2/3 * 2 + 0) / 3 = 4/9, losses (1/3 * 2 + 1) / 3 = 5/9 -> 44.44.
    const [first, second] = values(rsi(points([1, 2, 1, 2, 1]), 3))
    expect(first).toBeCloseTo(66.667, 2)
    expect(second).toBeCloseTo(44.444, 2)
  })

  it('is 100 when prices only rise and 0 when they only fall', () => {
    expect(values(rsi(points([1, 2, 3, 4, 5]), 3))).toEqual([100, 100])
    expect(values(rsi(points([5, 4, 3, 2, 1]), 3))).toEqual([0, 0])
  })

  it('needs `period` changes before the first value', () => {
    expect(rsi(points([1, 2, 3]), 14)).toEqual([])
    expect(rsi(points(Array.from({ length: 15 }, (_, i) => i)), 14)).toHaveLength(1)
  })
})
