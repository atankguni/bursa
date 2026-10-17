import { useState, type FormEvent } from 'react'
import { useMutation } from '@tanstack/react-query'
import { KeyRound } from 'lucide-react'
import { changePassword, errorMessage } from '../api'
import TwoFactorSettings from '../components/TwoFactorSettings'
import { useAuth } from '../lib/auth'
import { Field, FormError } from './auth/AuthLayout'

const primaryBtn =
  'rounded bg-accent px-3 py-1.5 text-xs font-medium text-accent-ink transition hover:opacity-90 disabled:opacity-50'
const secondaryBtn =
  'rounded px-3 py-1.5 text-xs font-medium text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink'

/** Settings → Security: password, then two-factor authentication. */
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
    </div>
  )
}

function PasswordCard() {
  const [editing, setEditing] = useState(false)
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const save = useMutation({
    mutationFn: () => changePassword(current, next),
    onSuccess: () => close(),
  })
  const mismatch = confirm !== '' && confirm !== next

  function close() {
    setEditing(false)
    setCurrent('')
    setNext('')
    setConfirm('')
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!mismatch) save.mutate()
  }

  return (
    <section className="rounded-md bg-panelalt/40 p-4 ring-1 ring-line">
      <div className="mb-2 flex items-center gap-2">
        <span className="text-accent">
          <KeyRound size={16} />
        </span>
        <h3 className="text-sm font-semibold">Password</h3>
      </div>
      <div className="space-y-3 text-xs text-muted">
        {editing ? (
          <form onSubmit={onSubmit} className="max-w-sm space-y-3">
            <Field
              label="Current password"
              type="password"
              autoComplete="current-password"
              autoFocus
              required
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
            />
            <Field
              label="New password"
              type="password"
              autoComplete="new-password"
              required
              value={next}
              onChange={(e) => setNext(e.target.value)}
            />
            <Field
              label="Confirm new password"
              type="password"
              autoComplete="new-password"
              required
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
            <FormError>
              {mismatch
                ? "Passwords don't match."
                : save.isError &&
                  errorMessage(save.error, "Couldn't change the password.")}
            </FormError>
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={save.isPending || mismatch}
                className={primaryBtn}
              >
                {save.isPending ? 'Saving…' : 'Change password'}
              </button>
              <button
                type="button"
                onClick={() => {
                  close()
                  save.reset()
                }}
                className={secondaryBtn}
              >
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <>
            <p>
              {save.isSuccess
                ? 'Password changed. Your other browsers and devices were signed out.'
                : 'Changing it signs you out on your other browsers and devices.'}
            </p>
            <button
              onClick={() => {
                save.reset()
                setEditing(true)
              }}
              className={secondaryBtn}
            >
              Change password
            </button>
          </>
        )}
      </div>
    </section>
  )
}
