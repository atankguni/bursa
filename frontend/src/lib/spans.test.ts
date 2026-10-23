import { afterEach, describe, expect, it, vi } from 'vitest'
import { spanStart } from './spans'

describe('spanStart', () => {
  afterEach(() => vi.useRealTimers())

  it('counts back from now', () => {
    vi.useFakeTimers({ now: Date.parse('2026-10-23T00:00:00Z') })
    expect(spanStart('1m')).toBe('2026-09-22T00:00:00.000Z')
    expect(spanStart('1y')).toBe('2025-10-22T00:00:00.000Z')
  })

  it('has no start for Max (fit everything)', () => {
    expect(spanStart('max')).toBeUndefined()
  })
})
