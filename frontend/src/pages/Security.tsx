import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { KeyRound } from 'lucide-react'
import { RecentActivity, SignedInDevices } from '../components/AccountActivity'
import ChangePasswordForm from '../components/ChangePasswordForm'
import TwoFactorSettings from '../components/TwoFactorSettings'
import { ME_KEY, useAuth } from '../lib/auth'

const secondaryBtn =
  'rounded-sm px-3 py-1.5 text-xs font-medium text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink'

/** Settings → Security: password, two-factor authentication, devices, activity. */
export default function Security() {
  const { user } = useAuth()
  return (
    <div className="space-y-4">
      <PasswordCard />

      <div className="space-y-3">
        <div>
          <h3 className="text-sm font-semibold">Two-factor authentication</h3>
          <p className="mt-0.5 text-xs text-muted">
            After your password, Bursa asks for a code, so a stolen password alone
            can&apos;t open your account.
            {user?.role === 'admin'
              ? ' Required for admins.'
              : ' Optional, and strongly recommended.'}{' '}
            A password reset doesn&apos;t turn it off.
          </p>
        </div>
        <TwoFactorSettings />
      </div>

      <SignedInDevices />
      <RecentActivity />
    </div>
  )
}

function PasswordCard() {
  const qc = useQueryClient()
  const { user } = useAuth()
  const [editing, setEditing] = useState(false)
  const [changed, setChanged] = useState(false)

  return (
    <section className="rounded-md bg-panelalt/40 p-4 ring-1 ring-line">
      <div className="mb-2 flex items-center gap-2">
        <span className="text-accent">
          <KeyRound size={16} />
        </span>
        <h3 className="text-sm font-semibold">Password</h3>
        {user?.password_weak && !changed && (
          <span className="ml-auto text-xs font-medium text-amber-700 dark:text-amber-400">
            Weak
          </span>
        )}
      </div>
      <div className="space-y-3 text-xs text-muted">
        {editing ? (
          <ChangePasswordForm
            onDone={() => {
              setEditing(false)
              setChanged(true)
              void qc.invalidateQueries({ queryKey: ME_KEY }) // clears the "weak" flag
            }}
            onCancel={() => setEditing(false)}
          />
        ) : (
          <>
            <p>
              {changed
                ? 'Password changed. Your other browsers and devices were signed out.'
                : user?.password_weak
                  ? 'Your password is easy to guess or appeared in a data breach. Change it to keep your account safe.'
                  : 'Changing it signs you out on your other browsers and devices.'}
            </p>
            <button onClick={() => setEditing(true)} className={secondaryBtn}>
              Change password
            </button>
          </>
        )}
      </div>
    </section>
  )
}
