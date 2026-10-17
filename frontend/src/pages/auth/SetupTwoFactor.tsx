import { ShieldCheck } from 'lucide-react'
import TwoFactorSettings from '../../components/TwoFactorSettings'
import { useAuth } from '../../lib/auth'

/** Admins without 2FA land here: the app opens once a method is turned on. */
export default function SetupTwoFactor() {
  const { user, signOut } = useAuth()
  return (
    <div className="flex min-h-full justify-center bg-app px-4 py-10 text-ink">
      <div className="w-full max-w-xl">
        <div className="mb-4 flex items-center gap-2">
          <ShieldCheck size={18} className="text-accent" />
          <h1 className="text-base font-semibold">Set up two-factor authentication</h1>
        </div>
        <p className="mb-5 text-sm text-muted">
          Admin accounts can manage users and the server, so they need a second step after the
          password. Set up an authenticator app (or email codes) to continue
          {user ? ` as ${user.email}` : ''}.
        </p>
        <TwoFactorSettings />
        <button
          onClick={() => void signOut()}
          className="mt-6 text-xs text-muted hover:text-ink"
        >
          Sign out
        </button>
      </div>
    </div>
  )
}
