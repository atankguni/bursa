import { describe, expect, it } from 'vitest'
import { DEFAULT_SETTINGS, fromStorage, type Settings } from './settings'

const base: Settings = DEFAULT_SETTINGS

describe('fromStorage', () => {
  it('keeps every stored value that is still valid', () => {
    const stored: Settings = {
      ...base,
      theme: 'dark',
      accent: 'violet',
      density: 'compact',
      chartType: 'candle',
      refreshSeconds: 120,
      numberFormat: 'full',
      defaultIndexes: ['IDX30'],
      hiddenColumns: { home: ['volume'], watchlist: ['pbv', 'roe'] },
      hidePortfolioValues: true,
    }
    expect(fromStorage(base, stored)).toEqual(stored)
  })

  it('falls back per field when a value has the wrong kind', () => {
    const result = fromStorage(base, {
      theme: 'sepia', // not a theme
      accent: 'orange', // not an accent
      autoRefresh: 'yes', // not a boolean
      refreshSeconds: Number.NaN, // not a finite number
      defaultIndexes: ['LQ45', 7], // not all strings
      chartRange: '1m', // valid: kept
    })
    expect(result).toEqual({ ...base, chartRange: '1m' })
  })

  it('checks the two hidden-column lists separately', () => {
    const result = fromStorage(base, {
      hiddenColumns: { home: 'volume', watchlist: ['pbv'] },
    })
    expect(result.hiddenColumns).toEqual({
      home: base.hiddenColumns.home,
      watchlist: ['pbv'],
    })
  })

  it('returns the defaults for anything that is not an object', () => {
    for (const stored of [null, undefined, 'dark', 42, true]) {
      expect(fromStorage(base, stored)).toEqual(base)
    }
  })

  it('ignores keys it does not know', () => {
    expect(fromStorage(base, { fontSize: 18 })).toEqual(base)
  })
})
