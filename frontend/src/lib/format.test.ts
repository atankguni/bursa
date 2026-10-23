import { afterEach, describe, expect, it } from 'vitest'
import {
  fmtChange,
  fmtCompact,
  fmtPct,
  fmtPercent,
  fmtPrice,
  fmtRatio,
  fmtTimeAgo,
  parseServerTime,
  setCompactNumbers,
} from './format'

describe('numbers', () => {
  afterEach(() => setCompactNumbers(true))

  it('shows a dash for missing values', () => {
    expect(fmtPrice(null)).toBe('—')
    expect(fmtCompact(undefined)).toBe('—')
    expect(fmtRatio(null)).toBe('—')
    expect(fmtPercent(null)).toBe('—')
    // Changes are left blank instead (they sit next to a price).
    expect(fmtChange(null)).toBe('')
    expect(fmtPct(undefined)).toBe('')
  })

  it('prints prices with separators and at most two decimals', () => {
    expect(fmtPrice(9875)).toBe('9,875')
    expect(fmtPrice(1234.567)).toBe('1,234.57')
  })

  it('abbreviates large numbers in compact mode', () => {
    expect(fmtCompact(1_234_000_000_000)).toBe('1.23T')
    expect(fmtCompact(-5_600_000_000)).toBe('-5.60B')
    expect(fmtCompact(7_890_000)).toBe('7.89M')
    expect(fmtCompact(12_345)).toBe('12.3K')
    expect(fmtCompact(999)).toBe('999')
  })

  it('prints every digit in full mode', () => {
    setCompactNumbers(false)
    expect(fmtCompact(1_234_000_000_000)).toBe('1,234,000,000,000')
  })

  it('signs changes', () => {
    expect(fmtChange(25)).toBe('+25.00')
    expect(fmtChange(-25)).toBe('-25.00')
    expect(fmtChange(0)).toBe('0.00')
    expect(fmtPct(1.234)).toBe('+1.23%')
    expect(fmtPct(-0.5)).toBe('-0.50%')
    expect(fmtPct(0)).toBe('0.00%')
  })

  it('turns fractions into percentages', () => {
    expect(fmtPercent(0.2134)).toBe('21.34%')
    expect(fmtPercent(0.2134, 0)).toBe('21%')
    expect(fmtRatio(4.567)).toBe('4.57')
  })
})

describe('parseServerTime', () => {
  it('reads timestamps without an offset as UTC', () => {
    expect(parseServerTime('2026-10-16T03:52:00')?.toISOString()).toBe(
      '2026-10-16T03:52:00.000Z',
    )
  })

  it('keeps an explicit offset', () => {
    expect(parseServerTime('2026-10-16T10:52:00+07:00')?.toISOString()).toBe(
      '2026-10-16T03:52:00.000Z',
    )
    expect(parseServerTime('2026-10-16T03:52:00Z')?.toISOString()).toBe(
      '2026-10-16T03:52:00.000Z',
    )
  })

  it('reads a bare date as that day in UTC', () => {
    expect(parseServerTime('2026-10-16')?.toISOString()).toBe('2026-10-16T00:00:00.000Z')
  })

  it('returns null for nothing or garbage', () => {
    expect(parseServerTime(null)).toBeNull()
    expect(parseServerTime('')).toBeNull()
    expect(parseServerTime('not a date')).toBeNull()
  })
})

describe('fmtTimeAgo', () => {
  const now = Date.parse('2026-10-23T12:00:00Z')
  const ago = (ms: number) => new Date(now - ms).toISOString()

  it('rounds to the largest sensible unit', () => {
    expect(fmtTimeAgo(ago(20_000), now)).toBe('just now')
    expect(fmtTimeAgo(ago(5 * 60_000), now)).toBe('5m ago')
    expect(fmtTimeAgo(ago(3 * 3_600_000), now)).toBe('3h ago')
    expect(fmtTimeAgo(ago(2 * 86_400_000), now)).toBe('2d ago')
  })

  it('treats a time in the future (clock skew) as just now', () => {
    expect(fmtTimeAgo(ago(-60_000), now)).toBe('just now')
  })

  it('shows a dash for no time', () => {
    expect(fmtTimeAgo(null, now)).toBe('—')
  })
})
