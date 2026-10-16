import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { setCompactNumbers } from './format'

export type Theme = 'system' | 'light' | 'dark'
export type Density = 'compact' | 'medium' | 'large'
export type NumberFormat = 'compact' | 'full'
type Resolved = 'light' | 'dark'

export interface Settings {
  // Appearance
  theme: Theme
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
  density: 'medium',
  reduceMotion: false,
  highContrast: false,
  defaultIndexes: ['LQ45'],
  chartType: 'candle',
  chartRange: '1d',
  autoRefresh: true,
  refreshSeconds: 60,
  numberFormat: 'compact',
  colorizeChanges: true,
  hiddenColumns: { home: [], watchlist: [] },
  hidePortfolioValues: false,
}

const STORAGE_KEY = 'bursa-settings'
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
  useEffect(() => {
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

  // Density + reduce-motion + high-contrast -> data attributes on <html>.
  useEffect(() => {
    const el = document.documentElement
    el.setAttribute('data-density', settings.density)
    el.toggleAttribute('data-reduce-motion', settings.reduceMotion)
    el.toggleAttribute('data-high-contrast', settings.highContrast)
  }, [settings.density, settings.reduceMotion, settings.highContrast])

  // Number format -> module-level formatter flag (keeps call sites unchanged).
  useEffect(() => {
    setCompactNumbers(settings.numberFormat === 'compact')
  }, [settings.numberFormat])

  const value = useMemo<SettingsContextValue>(
    () => ({
      settings,
      resolvedTheme,
      update: (partial) => setSettings((s) => ({ ...s, ...partial })),
      reset: () => setSettings(DEFAULT_SETTINGS),
    }),
    [settings, resolvedTheme],
  )

  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>
}

export function useSettings(): SettingsContextValue {
  const ctx = useContext(SettingsContext)
  if (!ctx) throw new Error('useSettings must be used within SettingsProvider')
  return ctx
}
