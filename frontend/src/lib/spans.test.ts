import { afterEach, describe, expect, it, vi } from 'vitest'
import { spanStart } from './spans'

describe('spanStart', () => {
  afterEach(() => vi.useRealTimers())

  it('counts back from now', () => {
    vi.useFakeTimers({ now: Date.parse('2026-10-23T00:00:00Z') })
    expect(spanStart('1m')).toBe('2026-09-22T00:00:00Z')
    expect(spanStart('1y')).toBe('2025-10-22T00:00:00Z')
  })

  it('stays the same through the day (so re-renders keep the zoom)', () => {
    vi.useFakeTimers({ now: Date.parse('2026-10-23T08:15:00Z') })
    const morning = spanStart('1y')
    vi.setSystemTime(Date.parse('2026-10-23T15:40:00Z'))
    expect(spanStart('1y')).toBe(morning)
    expect(morning).toBe('2025-10-22T00:00:00Z')
  })

  it('has no start for Max (fit everything)', () => {
    expect(spanStart('max')).toBeUndefined()
  })
})
