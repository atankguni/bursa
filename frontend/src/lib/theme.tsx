import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'

export type ThemeChoice = 'system' | 'light' | 'dark'
type Resolved = 'light' | 'dark'

interface ThemeContextValue {
  theme: ThemeChoice
  resolved: Resolved
  setTheme: (t: ThemeChoice) => void
}

const STORAGE_KEY = 'bursa-theme'
const ThemeContext = createContext<ThemeContextValue | null>(null)

const prefersDark = () =>
  typeof window !== 'undefined' &&
  window.matchMedia('(prefers-color-scheme: dark)').matches

function initial(): ThemeChoice {
  if (typeof window === 'undefined') return 'system'
  const stored = window.localStorage.getItem(STORAGE_KEY) as ThemeChoice | null
  return stored ?? 'system'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeChoice>(initial)
  const [resolved, setResolved] = useState<Resolved>(() =>
    (theme === 'system' ? prefersDark() : theme === 'dark') ? 'dark' : 'light',
  )

  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')

    const apply = () => {
      // "system" tracks the OS setting; pinned choices win.
      const dark =
        theme === 'dark' || (theme === 'system' && mq.matches)
      document.documentElement.classList.toggle('dark', dark)
      setResolved(dark ? 'dark' : 'light')
    }

    apply()
    if (theme === 'system') {
      mq.addEventListener('change', apply)
      return () => mq.removeEventListener('change', apply)
    }
  }, [theme])

  const setTheme = (t: ThemeChoice) => {
    window.localStorage.setItem(STORAGE_KEY, t)
    setThemeState(t)
  }

  return (
    <ThemeContext.Provider value={{ theme, resolved, setTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider')
  return ctx
}
