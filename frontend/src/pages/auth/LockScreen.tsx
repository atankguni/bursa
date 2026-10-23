import { useState, type FormEvent } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Lock } from 'lucide-react'
import { errorMessage, errorStatus, unlockSession, type Me } from '../../api'
import { useAuth } from '../../lib/auth'
import AuthLayout, { Field, FormError, primaryBtn } from './AuthLayout'

/** Shown instead of the app after inactivity: the password (no 2FA code) unlocks it. */
export default function LockScreen({ user }: { user: Me }) {
  const { unlocked, signOut } = useAuth()
  const [password, setPassword] = useState('')
  const unlock = useMutation({
    mutationFn: () => unlockSession(password),
    onSuccess: unlocked,
    onError: (error) => {
      setPassword('')
      // Too many wrong passwords: the server signed this browser out.
      if (errorStatus(error) === 401) void signOut()
    },
  })

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    unlock.mutate()
  }

  return (
    <AuthLayout
      title="Bursa is locked"
      subtitle={`Locked after inactivity. Enter your password to continue, ${user.name}.`}
    >
      <form onSubmit={onSubmit} className="space-y-3">
        <div className="flex items-center gap-2 rounded-sm bg-panelalt/70 px-3 py-2 text-xs ring-1 ring-line">
          <Lock size={14} className="shrink-0 text-accent" aria-hidden />
          <span className="truncate text-muted">{user.email}</span>
        </div>
        {/* Lets password managers match the saved login. */}
        <input type="email" autoComplete="username" value={user.email} readOnly hidden />
        <Field
          label="Password"
          type="password"
          autoComplete="current-password"
          autoFocus
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <FormError>
          {unlock.isError && errorMessage(unlock.error, "Couldn't unlock.")}
        </FormError>
        <button type="submit" disabled={unlock.isPending} className={primaryBtn}>
          {unlock.isPending ? 'Unlocking…' : 'Unlock'}
        </button>
        <button
          type="button"
          onClick={() => void signOut()}
          className="w-full text-center text-xs text-muted hover:text-ink"
        >
          Not you? Sign out
        </button>
      </form>
    </AuthLayout>
  )
}
