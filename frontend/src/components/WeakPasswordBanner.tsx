import { useState } from 'react'
import { Link } from 'react-router-dom'
import { KeyRound, X } from 'lucide-react'
import { useAuth } from '../lib/auth'

const DISMISSED_KEY = 'bursa-weak-password-dismissed'

/** Reminder for users whose password is weak or leaked (admins must change it). */
export default function WeakPasswordBanner() {
  const { user } = useAuth()
  const [dismissed, setDismissed] = useState(() => {
    try {
      return sessionStorage.getItem(DISMISSED_KEY) === '1'
    } catch {
      return false
    }
  })
  if (!user?.password_weak || dismissed) return null

  const dismiss = () => {
    setDismissed(true)
    try {
      sessionStorage.setItem(DISMISSED_KEY, '1') // back on the next visit
    } catch {
      /* private mode: just for this page */
    }
  }

  return (
    <div className="flex items-center gap-2 border-b border-amber-500/20 bg-amber-500/10 px-4 py-2 text-xs text-amber-700 dark:text-amber-400">
      <KeyRound size={14} className="shrink-0" />
      <p className="flex-1">
        Your password is easy to guess or appeared in a data breach.{' '}
        <Link
          to="/settings/security"
          className="font-medium underline underline-offset-2"
        >
          Change it
        </Link>{' '}
        to keep your account safe.
      </p>
      <button
        onClick={dismiss}
        aria-label="Dismiss"
        className="rounded p-1 hover:bg-amber-500/10"
      >
        <X size={14} />
      </button>
    </div>
  )
}
