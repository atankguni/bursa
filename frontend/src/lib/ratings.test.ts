import { describe, expect, it } from 'vitest'
import {
  isPositive,
  RATING_LABEL,
  RATING_ORDER,
  ratingLabel,
  ratingTone,
} from './ratings'

describe('ratings', () => {
  it('labels every rating, each differently, never as buy/sell advice', () => {
    const labels = RATING_ORDER.map(ratingLabel)
    expect(new Set(labels).size).toBe(RATING_ORDER.length)
    expect(Object.keys(RATING_LABEL).sort()).toEqual([...RATING_ORDER].sort())
    for (const label of labels) expect(label).not.toMatch(/buy|sell|hold|avoid|reduce/i)
  })

  it('orders best first', () => {
    expect(RATING_ORDER[0]).toBe('Strong Buy')
    expect(RATING_ORDER[RATING_ORDER.length - 1]).toBe('Avoid')
  })

  it('colours positive green, negative red and neutral muted', () => {
    expect(RATING_ORDER.map(ratingTone)).toEqual([
      'text-bull',
      'text-bull',
      'text-muted',
      'text-bear',
      'text-bear',
    ])
    expect(isPositive('Buy')).toBe(true)
    expect(isPositive('Hold')).toBe(false)
    expect(isPositive(null)).toBe(false)
  })
})
