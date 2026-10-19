import {
  createContext,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'

import { fetchPreferences, updatePreferences, type DisplaySettings } from '../api'
import { queryKeys } from '../hooks/keys'
import { useAuth } from './auth'
import { setCompactNumbers } from './format'

export type Theme = 'system' | 'light' | 'dark'
export type Density = 'compact' | 'medium' | 'large'
export type NumberFormat = 'compact' | 'full'
/** UI accent colour; the shades live in index.css (`data-accent`). */
export type Accent = 'blue' | 'indigo' | 'violet' | 'graphite'
export const ACCENTS: { value: Accent; label: string }[] = [
  { value: 'blue', label: 'Blue' },
  { value: 'indigo', label: 'Indigo' },
  { value: 'violet', label: 'Violet' },
  { value: 'graphite', label: 'Graphite' },
]
type Resolved = 'light' | 'dark'

export interface Settings {
  // Appearance
  theme: Theme
  accent: Accent
  density: Density
  reduceMotion: boolean
  highContrast: boolean
  // Data / Display
  defaultIndexes: string[]
  chartType: 'candle' | 'line'
  chartRange: '1d' | '1m'
  autoRefresh: boolean
  refreshSeconds: number
  numberFormat: NumberFormat
  colorizeChanges: boolean
  hiddenColumns: { home: string[]; watchlist: string[] }
  // Privacy
  hidePortfolioValues: boolean
}

export const DEFAULT_SETTINGS: Settings = {
  theme: 'system',
  accent: 'blue',
  density: 'medium',
  reduceMotion: false,
  highContrast: false,
  defaultIndexes: ['LQ45'],
  chartType: 'line',
  chartRange: '1d',
  autoRefresh: true,
  refreshSeconds: 60,
  numberFormat: 'compact',
  colorizeChanges: true,
  hiddenColumns: { home: [], watchlist: [] },
  hidePortfolioValues: false,
}

/**
 * Saved per user on the server, so they follow the user across devices. The
 * rest (theme, accent, density, motion, contrast, "hide portfolio values")
 * depends on the screen, so it stays in this browser only.
 */
export const ACCOUNT_KEYS = [
  'defaultIndexes',
  'chartType',
  'chartRange',
  'autoRefresh',
  'refreshSeconds',
  'numberFormat',
  'colorizeChanges',
  'hiddenColumns',
] as const satisfies readonly (keyof Settings & keyof DisplaySettings)[]

const accountPart = (s: Settings): DisplaySettings =>
  Object.fromEntries(ACCOUNT_KEYS.map((k) => [k, s[k]])) as unknown as DisplaySettings

// A local copy of everything, so the page renders with the right settings at once.
const STORAGE_KEY = 'bursa-settings'
// Which account the local copy's account part came from (unset: from before accounts).
const OWNER_KEY = 'bursa-settings-owner'

function readOwner(): string | null {
  try {
    return window.localStorage.getItem(OWNER_KEY)
  } catch {
    return null
  }
}

function writeOwner(userId: number | null) {
  try {
    if (userId === null) window.localStorage.removeItem(OWNER_KEY)
    else window.localStorage.setItem(OWNER_KEY, String(userId))
  } catch {
    /* ignore */
  }
}
const LEGACY_THEME_KEY = 'bursa-theme'

const prefersDark = () =>
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-color-scheme: dark)').matches

const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

/** Load settings, migrating the legacy single theme key if present. */
function load(): Settings {
  if (typeof window === 'undefined') return DEFAULT_SETTINGS
  // Default motion to the OS preference until the user chooses explicitly.
  const base: Settings = { ...DEFAULT_SETTINGS, reduceMotion: prefersReducedMotion() }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<Settings>
      return {
        ...base,
        ...parsed,
        hiddenColumns: {
          ...base.hiddenColumns,
          ...(parsed.hiddenColumns ?? {}),
        },
      }
    }
    const legacy = window.localStorage.getItem(LEGACY_THEME_KEY) as Theme | null
    if (legacy) return { ...base, theme: legacy }
  } catch {
    /* ignore malformed storage */
  }
  return DEFAULT_SETTINGS
}

interface SettingsContextValue {
  settings: Settings
  resolvedTheme: Resolved
  update: (partial: Partial<Settings>) => void
  reset: () => void
}

const SettingsContext = createContext<SettingsContextValue | null>(null)

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings>(load)
  const sync = useAccountSync(settings, setSettings)
  const [resolvedTheme, setResolvedTheme] = useState<Resolved>(() =>
    (settings.theme === 'system' ? prefersDark() : settings.theme === 'dark')
      ? 'dark'
      : 'light',
  )

  // Persist on every change.
  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
    } catch {
      /* ignore quota / privacy-mode errors */
    }
  }, [settings])

  // Theme -> `.dark` class (+ follow the OS when set to "system").
  // Layout effects (here and below): they run before any child's useEffect, so
  // charts reading CSS variables (readCssColor) see the new theme and accent.
  useLayoutEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const apply = () => {
      const dark =
        settings.theme === 'dark' || (settings.theme === 'system' && mq.matches)
      document.documentElement.classList.toggle('dark', dark)
      setResolvedTheme(dark ? 'dark' : 'light')
    }
    apply()
    if (settings.theme === 'system') {
      mq.addEventListener('change', apply)
      return () => mq.removeEventListener('change', apply)
    }
  }, [settings.theme])

  // Accent + density + reduce-motion + high-contrast -> data attributes on <html>.
  useLayoutEffect(() => {
    const el = document.documentElement
    el.setAttribute('data-accent', settings.accent)
    el.setAttribute('data-density', settings.density)
    el.toggleAttribute('data-reduce-motion', settings.reduceMotion)
    el.toggleAttribute('data-high-contrast', settings.highContrast)
  }, [settings.accent, settings.density, settings.reduceMotion, settings.highContrast])

  // Number format -> module-level formatter flag (keeps call sites unchanged).
  useEffect(() => {
    setCompactNumbers(settings.numberFormat === 'compact')
  }, [settings.numberFormat])

  const value = useMemo<SettingsContextValue>(
    () => ({
      settings,
      resolvedTheme,
      update: (partial) => {
        if (ACCOUNT_KEYS.some((k) => k in partial)) sync.markChanged()
        setSettings((s) => ({ ...s, ...partial }))
      },
      reset: () => {
        sync.markChanged()
        setSettings(DEFAULT_SETTINGS)
      },
    }),
    [settings, resolvedTheme, sync],
  )

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>
}

/**
 * Keeps the account part of the settings in step with the signed-in user's
 * saved copy: applies it after sign-in, saves changes (debounced), uploads this
 * browser's settings the first time a user has none, and returns to defaults on
 * sign-out so the next person on this browser doesn't inherit them.
 */
function useAccountSync(
  settings: Settings,
  setSettings: (update: (s: Settings) => Settings) => void,
) {
  const { user } = useAuth()
  const qc = useQueryClient()
  const { data: prefs } = useQuery({
    queryKey: queryKeys.preferences,
    queryFn: fetchPreferences,
    staleTime: Infinity,
    enabled: !!user,
  })
  // The user whose saved settings are applied; saving waits for it so this
  // browser's copy never overwrites the account's before it has loaded.
  const syncedFor = useRef<number | null>(null)
  const changed = useRef(false)
  const latest = useRef(settings)
  latest.current = settings

  const save = useMemo(
    () => (display: DisplaySettings) =>
      updatePreferences({ display })
        .then((saved) => qc.setQueryData(queryKeys.preferences, saved))
        .catch(() => {
          /* offline or signed out: kept locally; saved with the next change */
        }),
    [qc],
  )

  // Pull: apply the signed-in user's settings once they load.
  useEffect(() => {
    if (user === null && syncedFor.current !== null) {
      syncedFor.current = null
      changed.current = false
      writeOwner(null)
      setSettings((s) => ({ ...s, ...accountPart(DEFAULT_SETTINGS) }))
      return
    }
    if (!user || !prefs || syncedFor.current === user.id) return
    syncedFor.current = user.id
    changed.current = false
    const owner = readOwner()
    writeOwner(user.id)
    if (prefs.display) {
      const display = prefs.display
      setSettings((s) => ({ ...s, ...display }))
    } else if (owner === null || owner === String(user.id)) {
      void save(accountPart(latest.current)) // first time: keep what this browser had
    } else {
      // This browser's copy belongs to someone else: start from the defaults.
      setSettings((s) => ({ ...s, ...accountPart(DEFAULT_SETTINGS) }))
      void save(accountPart(DEFAULT_SETTINGS))
    }
  }, [user, prefs, save, setSettings])

  // Push: save account changes, debounced (a slider or several toggles = one save).
  useEffect(() => {
    if (!changed.current || !user || syncedFor.current !== user.id) return
    const t = setTimeout(() => {
      changed.current = false
      void save(accountPart(settings))
    }, 600)
    return () => clearTimeout(t)
  }, [settings, user, save])

  return useMemo(() => ({ markChanged: () => (changed.current = true) }), [])
}

/**
 * A colour token from index.css (e.g. "--c-accent") as a hex string, for canvas
 * libraries such as the charts that can't use CSS variables directly.
 */
export function readCssColor(token: string, fallback = '#2563eb'): string {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(token).trim()
  const parts = raw.split(/\s+/).map(Number)
  if (parts.length !== 3 || parts.some((n) => !Number.isFinite(n))) return fallback
  return `#${parts.map((n) => n.toString(16).padStart(2, '0')).join('')}`
}

export function useSettings(): SettingsContextValue {
  const ctx = useContext(SettingsContext)
  if (!ctx) throw new Error('useSettings must be used within SettingsProvider')
  return ctx
}
