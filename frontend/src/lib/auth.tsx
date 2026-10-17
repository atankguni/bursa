import { createContext, useCallback, useContext, useEffect, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchMe, logout, UNAUTHORIZED_EVENT, type Me } from '../api'

export const ME_KEY = ['auth', 'me'] as const

interface AuthState {
  /** undefined while the first check runs; null when signed out. */
  user: Me | null | undefined
  isAdmin: boolean
  /** After sign-in / invite acceptance: show the app for this user. */
  signedIn: (user: Me) => void
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  const { data: user } = useQuery({
    queryKey: ME_KEY,
    queryFn: fetchMe,
    staleTime: Infinity,
    retry: false,
  })

  // Another user's cached data must never show: start from an empty cache
  // whenever the account changes, keeping only the answer to "who am I".
  const reset = useCallback(
    (next: Me | null) => {
      qc.clear()
      qc.setQueryData(ME_KEY, next)
    },
    [qc],
  )

  useEffect(() => {
    const onUnauthorized = () => {
      if (qc.getQueryData(ME_KEY)) reset(null)
    }
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
  }, [qc, reset])

  const signOut = useCallback(async () => {
    try {
      await logout()
    } finally {
      reset(null)
    }
  }, [reset])

  return (
    <AuthContext.Provider
      value={{ user, isAdmin: user?.role === 'admin', signedIn: reset, signOut }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
