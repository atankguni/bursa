import { useQueryClient } from '@tanstack/react-query'
import { KeyRound } from 'lucide-react'
import ChangePasswordForm from '../../components/ChangePasswordForm'
import { ME_KEY, useAuth } from '../../lib/auth'

/** Admins whose password is weak or leaked land here: the app opens once it's changed. */
export default function ChangeWeakPassword() {
  const { user, signOut } = useAuth()
  const qc = useQueryClient()
  return (
    <div className="flex min-h-full justify-center bg-app px-4 py-10 text-ink">
      <div className="w-full max-w-xl">
        <div className="mb-4 flex items-center gap-2">
          <KeyRound size={18} className="text-accent" />
          <h1 className="text-base font-semibold">Choose a stronger password</h1>
        </div>
        <p className="mb-5 text-sm text-muted">
          The password of {user ? user.email : 'this account'} is easy to guess or
          appeared in a data breach. Admin accounts can manage users and the server, so
          choose a new one to continue. Your other browsers and devices will be signed
          out.
        </p>
        <div className="rounded-md bg-panelalt/40 p-4 ring-1 ring-line">
          <ChangePasswordForm
            onDone={() => void qc.invalidateQueries({ queryKey: ME_KEY })}
          />
        </div>
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
