import { createContext, useCallback, useContext, useEffect, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  fetchMe,
  LOCKED_EVENT,
  lockSession,
  logout,
  MFA_SETUP_EVENT,
  UNAUTHORIZED_EVENT,
  type Me,
} from '../api'

export const ME_KEY = ['auth', 'me'] as const

interface AuthState {
  /** undefined while the first check runs; null when signed out. */
  user: Me | null | undefined
  isAdmin: boolean
  /** After sign-in / invite acceptance: show the app for this user. */
  signedIn: (user: Me) => void
  signOut: () => Promise<void>
  /** Lock this browser (idle timer or "Lock now"); every tab shows the lock screen. */
  lock: () => Promise<void>
  /** After the lock screen accepted the password: back to the app, in every tab. */
  unlocked: (user: Me) => void
}

// Tabs of this browser share one session, so they lock and unlock together.
const LOCK_CHANNEL = 'bursa-lock'
type LockMessage = 'locked' | 'unlocked'

function lockChannel(): BroadcastChannel | null {
  try {
    return new BroadcastChannel(LOCK_CHANNEL)
  } catch {
    return null // very old browsers: each tab still locks on its own (423s)
  }
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

  // Locked: keep only "who am I" (now with locked: true). Cached data is dropped,
  // so nothing of it stays on the page or in memory behind the lock screen.
  const applyLocked = useCallback(() => {
    const me = qc.getQueryData<Me | null>(ME_KEY)
    if (me && !me.locked) reset({ ...me, locked: true })
  }, [qc, reset])

  useEffect(() => {
    const channel = lockChannel()
    const onLocked = () => applyLocked() // the API answered 423
    window.addEventListener(LOCKED_EVENT, onLocked)
    channel?.addEventListener('message', (e: MessageEvent<LockMessage>) => {
      if (e.data === 'locked') applyLocked()
      // Unlocked in another tab: /me now says so.
      else void qc.invalidateQueries({ queryKey: ME_KEY })
    })
    return () => {
      window.removeEventListener(LOCKED_EVENT, onLocked)
      channel?.close()
    }
  }, [qc, applyLocked])

  const broadcast = useCallback((message: LockMessage) => {
    const channel = lockChannel()
    // oxlint-disable-next-line unicorn/require-post-message-target-origin -- BroadcastChannel takes no origin
    channel?.postMessage(message)
    channel?.close()
  }, [])

  const lock = useCallback(async () => {
    try {
      await lockSession()
    } catch {
      // Offline: the server locks it anyway once it has been idle long enough.
    }
    applyLocked()
    broadcast('locked')
  }, [applyLocked, broadcast])

  const unlocked = useCallback(
    (me: Me) => {
      reset(me)
      broadcast('unlocked')
    },
    [reset, broadcast],
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
      value={{
        user,
        isAdmin: user?.role === 'admin',
        signedIn: reset,
        signOut,
        lock,
        unlocked,
      }}
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
