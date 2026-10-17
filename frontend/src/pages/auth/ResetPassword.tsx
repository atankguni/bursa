import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { checkResetToken, errorMessage, fetchAuthOptions, resetPassword } from '../../api'
import PasswordStrength from '../../components/PasswordStrength'
import { usePasswordStrength } from '../../lib/passwordStrength'
import AuthLayout, { Field, FormError, primaryBtn } from './AuthLayout'

export default function ResetPassword() {
  const { token = '' } = useParams()
  const check = useQuery({
    queryKey: ['auth', 'reset', token],
    queryFn: () => checkResetToken(token).then(() => true),
    retry: false,
  })
  const { data: options } = useQuery({
    queryKey: ['auth', 'options'],
    queryFn: fetchAuthOptions,
  })
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const submit = useMutation({ mutationFn: () => resetPassword(token, password) })
  const strength = usePasswordStrength(password)
  const signIn = (
    <Link to="/" className="hover:text-ink">
      Go to sign in
    </Link>
  )

  if (check.isPending) return <AuthLayout title="Checking your link…">{null}</AuthLayout>
  if (check.isError) {
    return (
      <AuthLayout title="Link not valid" footer={signIn}>
        <p className="text-sm text-muted">
          {errorMessage(check.error, 'This reset link is invalid or has expired.')}
        </p>
      </AuthLayout>
    )
  }
  if (submit.isSuccess) {
    return (
      <AuthLayout title="Password changed" footer={signIn}>
        <p className="text-sm text-muted">
          Sign in with your new password. Other browsers were signed out.
        </p>
      </AuthLayout>
    )
  }

  const mismatch = confirm !== '' && confirm !== password
  const minLength = options?.password_min_length ?? 12
  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!mismatch) submit.mutate()
  }
  return (
    <AuthLayout title="Choose a new password">
      <form onSubmit={onSubmit} className="space-y-3">
        <Field
          label="New password"
          type="password"
          autoComplete="new-password"
          autoFocus
          required
          minLength={minLength}
          hint={<PasswordStrength strength={strength} />}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <Field
          label="Confirm password"
          type="password"
          autoComplete="new-password"
          required
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
        <FormError>
          {mismatch
            ? "Passwords don't match."
            : submit.isError &&
              errorMessage(submit.error, "Couldn't change the password.")}
        </FormError>
        <button
          type="submit"
          disabled={submit.isPending || mismatch || strength?.acceptable === false}
          className={primaryBtn}
        >
          {submit.isPending ? 'Saving…' : 'Set password'}
        </button>
      </form>
    </AuthLayout>
  )
}
