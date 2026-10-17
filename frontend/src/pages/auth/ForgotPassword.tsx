import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { errorMessage, fetchAuthOptions, requestPasswordReset } from '../../api'
import AuthLayout, { Field, FormError, primaryBtn } from './AuthLayout'

export default function ForgotPassword() {
  const { data: options } = useQuery({ queryKey: ['auth', 'options'], queryFn: fetchAuthOptions })
  const [email, setEmail] = useState('')
  const submit = useMutation({ mutationFn: () => requestPasswordReset(email) })
  const back = <Link to="/" className="hover:text-ink">Back to sign in</Link>

  if (options && !options.password_reset_by_email) {
    return (
      <AuthLayout title="Forgot password" footer={back}>
        <p className="text-sm text-muted">
          Ask your admin for a password reset link. They can create one from the Users page.
        </p>
      </AuthLayout>
    )
  }
  if (submit.isSuccess) {
    return (
      <AuthLayout title="Check your email" footer={back}>
        <p className="text-sm text-muted">
          If <span className="text-ink">{email}</span> has an account, a reset link is on its
          way. It works once and expires in a couple of hours.
        </p>
      </AuthLayout>
    )
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    submit.mutate()
  }
  return (
    <AuthLayout
      title="Forgot password"
      subtitle="We'll email you a link to choose a new one."
      footer={back}
    >
      <form onSubmit={onSubmit} className="space-y-3">
        <Field
          label="Email"
          type="email"
          autoComplete="username"
          autoFocus
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <FormError>{submit.isError && errorMessage(submit.error, "Couldn't send the link.")}</FormError>
        <button type="submit" disabled={submit.isPending} className={primaryBtn}>
          {submit.isPending ? 'Sending…' : 'Send reset link'}
        </button>
      </form>
    </AuthLayout>
  )
}
