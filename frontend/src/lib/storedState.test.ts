import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  clearStoredViews,
  isStringArray,
  oneOf,
  readStored,
  storageKey,
} from './storedState'

function stubStorage(items: Record<string, string>) {
  vi.stubGlobal('window', { localStorage: { getItem: (k: string) => items[k] ?? null } })
}

describe('stored view choices', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('keeps each account apart', () => {
    expect(storageKey(3, 'home.sort')).toBe('bursa-view:3:home.sort')
    expect(storageKey(undefined, 'home.sort')).toBe('bursa-view:anon:home.sort')
  })

  it('reads a valid value back', () => {
    stubStorage({ k: '["LQ45","IDX30"]' })
    expect(readStored('k', isStringArray)).toEqual(['LQ45', 'IDX30'])
  })

  it('ignores a value of the wrong shape, bad JSON, or no storage at all', () => {
    const span = oneOf('1m', '1y')
    stubStorage({ a: '"5y"', b: '{oops', c: '42' })
    expect(readStored('a', span)).toBeUndefined()
    expect(readStored('b', span)).toBeUndefined()
    expect(readStored('c', isStringArray)).toBeUndefined()
    expect(readStored('missing', span)).toBeUndefined()
    vi.stubGlobal('window', {
      localStorage: {
        getItem: () => {
          throw new Error('blocked')
        },
      },
    })
    expect(readStored('a', span)).toBeUndefined()
  })

  it("reset forgets only that account's choices", () => {
    const items = new Map([
      ['bursa-view:3:home.sort', '1'],
      ['bursa-view:3:chart.span', '2'],
      ['bursa-view:30:home.sort', '3'],
      ['bursa-settings', '4'],
    ])
    vi.stubGlobal('window', {
      localStorage: {
        get length() {
          return items.size
        },
        key: (i: number) => [...items.keys()][i] ?? null,
        removeItem: (k: string) => items.delete(k),
      },
    })
    clearStoredViews(3)
    expect([...items.keys()]).toEqual(['bursa-view:30:home.sort', 'bursa-settings'])
  })
})
