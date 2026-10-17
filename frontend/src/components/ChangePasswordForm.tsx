import { useState, type FormEvent } from 'react'
import { useMutation } from '@tanstack/react-query'
import { changePassword, errorMessage } from '../api'
import { useAuth } from '../lib/auth'
import { usePasswordStrength } from '../lib/passwordStrength'
import { Field, FormError } from '../pages/auth/AuthLayout'
import PasswordStrength from './PasswordStrength'

const primaryBtn =
  'rounded bg-accent px-3 py-1.5 text-xs font-medium text-accent-ink transition hover:opacity-90 disabled:opacity-50'
const secondaryBtn =
  'rounded px-3 py-1.5 text-xs font-medium text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink'

/** Current + new password (with the strength meter) + confirmation. */
export default function ChangePasswordForm({
  onDone,
  onCancel,
}: {
  onDone: () => void
  onCancel?: () => void
}) {
  const { user } = useAuth()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const strength = usePasswordStrength(next, [user?.email ?? '', user?.name ?? ''])
  const save = useMutation({
    mutationFn: () => changePassword(current, next),
    onSuccess: onDone,
  })
  const mismatch = confirm !== '' && confirm !== next

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!mismatch) save.mutate()
  }

  return (
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
        hint={<PasswordStrength strength={strength} />}
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
          : save.isError && errorMessage(save.error, "Couldn't change the password.")}
      </FormError>
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={save.isPending || mismatch || strength?.acceptable === false}
          className={primaryBtn}
        >
          {save.isPending ? 'Saving…' : 'Change password'}
        </button>
        {onCancel && (
          <button type="button" onClick={onCancel} className={secondaryBtn}>
            Cancel
          </button>
        )}
      </div>
    </form>
  )
}
