import { describe, expect, it } from 'vitest'
import {
  estimateSale,
  floorToStep,
  onPriceStep,
  priceStep,
  sellableLots,
} from './sellEstimate'

describe('IDX price steps', () => {
  it('follows the price bands', () => {
    expect([150, 200, 499, 500, 1995, 2000, 4990, 5000, 9025].map(priceStep)).toEqual([
      1, 2, 2, 5, 5, 10, 10, 25, 25,
    ])
  })

  it('checks and rounds order prices', () => {
    expect(onPriceStep(9025)).toBe(true)
    expect(onPriceStep(9030)).toBe(false)
    expect(onPriceStep(0)).toBe(false)
    expect(floorToStep(9030)).toBe(9025)
    expect(floorToStep(1233)).toBe(1230)
  })
})

describe('estimateSale', () => {
  it('nets the sell fee and compares with the average cost', () => {
    // 10 lots of BBCA at 9,000; bought at 8,013.6 average (fees included).
    const e = estimateSale({
      shares: 1000,
      price: 9000,
      avgCost: 8013.6,
      sellFeePct: 0.2513,
    })
    expect(e.gross).toBe(9_000_000)
    expect(e.costs).toBe(22_617) // 0.2513% of 9,000,000 = 22,617
    expect(e.net).toBe(8_977_383)
    expect(e.costBasis).toBeCloseTo(8_013_600)
    expect(e.pl).toBeCloseTo(963_783)
    expect(e.plPct).toBeCloseTo(12.027, 2)
  })

  it('reports a loss, rounding the fee to whole rupiah', () => {
    const loss = estimateSale({ shares: 100, price: 50, avgCost: 60, sellFeePct: 0.25 })
    expect(loss.costs).toBe(13) // 12.5 rounds up
    expect(loss.net).toBe(4987)
    expect(loss.pl).toBe(-1013)
    expect(loss.plPct).toBeCloseTo(-16.883, 2)
  })

  it('handles a zero cost basis', () => {
    expect(
      estimateSale({ shares: 100, price: 50, avgCost: 0, sellFeePct: 0 }).plPct,
    ).toBeNull()
  })
})

describe('sellableLots', () => {
  it('splits whole lots from odd shares', () => {
    expect(sellableLots(1050, 100)).toEqual({ lots: 10, oddShares: 50 })
    expect(sellableLots(40, 100)).toEqual({ lots: 0, oddShares: 40 })
  })
})
