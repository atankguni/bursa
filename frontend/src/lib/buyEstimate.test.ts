import { describe, expect, it } from 'vitest'
import { affordableLots, breakEven, ceilToStep, estimateBuy } from './buyEstimate'

describe('buy estimate', () => {
  it('rounds prices up to the IDX step', () => {
    expect(ceilToStep(1001)).toBe(1005)
    expect(ceilToStep(4991)).toBe(5000)
    expect(ceilToStep(199.2)).toBe(200)
  })

  it('averages down, fees included', () => {
    // 10 lots at an average of 1,000 (fees in), buy 10 more at 800 with a 0.15% fee.
    const e = estimateBuy({
      heldShares: 1000,
      avgCost: 1000,
      buyShares: 1000,
      price: 800,
      buyFeePct: 0.15,
      sellFeePct: 0.25,
    })
    expect(e.fee).toBe(1200)
    expect(e.total).toBe(801_200)
    expect(e.avgCost).toBe(900.6)
    expect(e.avgChangePct).toBeCloseTo(-9.94, 2)
    // 900.6 / 0.9975 = 902.86 → next 5-rupiah step
    expect(e.breakEven).toBe(905)
    expect(e.breakEvenBefore).toBe(1005)
  })

  it('a first buy has no "before"', () => {
    const e = estimateBuy({
      heldShares: 0,
      avgCost: 0,
      buyShares: 100,
      price: 5000,
      buyFeePct: 0.15,
      sellFeePct: 0.25,
    })
    expect(e.avgChangePct).toBeNull()
    expect(e.breakEvenBefore).toBeNull()
    expect(e.avgCost).toBe(5007.5)
  })

  it('counts the lots a budget buys, fee included', () => {
    expect(affordableLots(1_000_000, 1000, 100, 0.15)).toBe(9) // 10 lots would be 1,001,500
    expect(affordableLots(1_001_500, 1000, 100, 0.15)).toBe(10)
    expect(affordableLots(0, 1000, 100, 0.15)).toBe(0)
    expect(breakEven(0, 0.25)).toBeNull()
  })
})
