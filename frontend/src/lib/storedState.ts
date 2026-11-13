import { useCallback, useState } from 'react'
import { useAuth } from './auth'

/**
 * A view choice remembered in this browser (sort column, filters, chart range):
 * a convenience, so a page reopens as it was left. Kept per account, so people
 * sharing a computer each get their own; a stored value that fails `isValid`
 * (an older format, edited by hand) is ignored in favour of `initial`.
 */

const PREFIX = 'bursa-view'

export function storageKey(userId: number | null | undefined, name: string): string {
  return `${PREFIX}:${userId ?? 'anon'}:${name}`
}

export function readStored<T>(
  key: string,
  isValid: (v: unknown) => v is T,
): T | undefined {
  try {
    const raw = window.localStorage.getItem(key)
    if (raw == null) return undefined
    const v: unknown = JSON.parse(raw)
    return isValid(v) ? v : undefined
  } catch {
    return undefined // storage blocked, or not JSON
  }
}

function writeStored(key: string, value: unknown) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* storage full or blocked: the choice just isn't remembered */
  }
}

function isUpdater<T>(next: T | ((prev: T) => T)): next is (prev: T) => T {
  return typeof next === 'function'
}

export function useStoredState<T>(
  name: string,
  initial: T,
  isValid: (v: unknown) => v is T,
): [T, (next: T | ((prev: T) => T)) => void] {
  const { user } = useAuth()
  const key = storageKey(user?.id, name)
  const [state, setState] = useState(() => ({
    key,
    value: readStored(key, isValid) ?? initial,
  }))
  // Another account signed in on this tab: its own stored value.
  const value = state.key === key ? state.value : (readStored(key, isValid) ?? initial)

  const set = useCallback(
    (next: T | ((prev: T) => T)) => {
      setState((s) => {
        const prev = s.key === key ? s.value : (readStored(key, isValid) ?? initial)
        const v = isUpdater(next) ? next(prev) : next
        writeStored(key, v)
        return { key, value: v }
      })
    },
    [key, isValid, initial],
  )
  return [value, set]
}

// Small validators for the common shapes.
export const isBool = (v: unknown): v is boolean => typeof v === 'boolean'
export const isString = (v: unknown): v is string => typeof v === 'string'
export const isNumber = (v: unknown): v is number =>
  typeof v === 'number' && Number.isFinite(v)
export const isStringArray = (v: unknown): v is string[] =>
  Array.isArray(v) && v.every((x) => typeof x === 'string')
export const oneOf =
  <T extends string | number>(...options: readonly T[]) =>
  (v: unknown): v is T =>
    options.some((o) => o === v)

const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v)

/** A {key, dir} table sort whose key is one of `keys`. */
export const isSortOf =
  <K extends string>(keys: readonly K[]) =>
  (v: unknown): v is { key: K; dir: 'asc' | 'desc' } =>
    isRecord(v) &&
    keys.some((k) => k === v['key']) &&
    (v['dir'] === 'asc' || v['dir'] === 'desc')

/** An object with exactly these boolean flags (e.g. chart indicators). */
export const isFlags =
  <K extends string>(keys: readonly K[]) =>
  (v: unknown): v is Record<K, boolean> =>
    isRecord(v) && keys.every((k) => typeof v[k] === 'boolean')

/** Forget every remembered view choice of one account (Settings → Reset). */
export function clearStoredViews(userId: number | null | undefined) {
  const prefix = storageKey(userId, '')
  try {
    const keys = Array.from({ length: window.localStorage.length }, (_, i) =>
      window.localStorage.key(i),
    )
    for (const k of keys) if (k?.startsWith(prefix)) window.localStorage.removeItem(k)
  } catch {
    /* storage blocked: nothing stored either */
  }
}
