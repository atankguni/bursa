import { createContext, useCallback, useContext, useEffect, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchMe, logout, MFA_SETUP_EVENT, UNAUTHORIZED_EVENT, type Me } from '../api'

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

  // Another user's cached data must never show: drop every cached query
  // whenever the account changes, keeping only the answer to "who am I".
  // (Not qc.clear(): that would also detach the useQuery above from the cache,
  // so this provider would never see the new user.)
  const reset = useCallback(
    (next: Me | null) => {
      qc.setQueryData(ME_KEY, next)
      const me = qc.getQueryCache().find({ queryKey: ME_KEY, exact: true })
      qc.removeQueries({ predicate: (q) => q !== me })
    },
    [qc],
  )

  useEffect(() => {
    const onUnauthorized = () => {
      if (qc.getQueryData(ME_KEY) !== null) reset(null)
    }
    // E.g. just promoted to admin: re-read /me, which shows the 2FA setup screen.
    const onMfaSetup = () => void qc.invalidateQueries({ queryKey: ME_KEY })
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
    window.addEventListener(MFA_SETUP_EVENT, onMfaSetup)
    return () => {
      window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
      window.removeEventListener(MFA_SETUP_EVENT, onMfaSetup)
    }
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
