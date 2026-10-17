import { ShieldCheck } from 'lucide-react'
import TwoFactorSettings from '../components/TwoFactorSettings'
import { useAuth } from '../lib/auth'

/** Account security: two-factor authentication. */
export default function Security() {
  const { user } = useAuth()
  return (
    <main className="w-full max-w-2xl animate-fade-in px-4 py-4">
      <div className="mb-3 flex items-center gap-2">
        <ShieldCheck size={16} className="text-accent" />
        <h2 className="text-sm font-semibold tracking-tight">Two-factor authentication</h2>
      </div>
      <p className="mb-4 text-xs text-muted">
        After your password, Bursa asks for a code, so a stolen password alone can&apos;t open
        your account.
        {user?.role === 'admin'
          ? ' Required for admins.'
          : ' Optional, and strongly recommended.'}{' '}
        A password reset doesn&apos;t turn it off.
      </p>
      <TwoFactorSettings />
    </main>
  )
}
