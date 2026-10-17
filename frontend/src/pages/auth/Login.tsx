import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { errorMessage, login } from '../../api'
import { useAuth } from '../../lib/auth'
import AuthLayout, { Field, FormError, primaryBtn } from './AuthLayout'

export default function Login() {
  const { signedIn } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const submit = useMutation({ mutationFn: () => login(email, password), onSuccess: signedIn })

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    submit.mutate()
  }

  return (
    <AuthLayout
      title="Sign in"
      subtitle="Bursa is invite-only. Ask your admin for an invite link."
      footer={<Link to="/forgot" className="hover:text-ink">Forgot password?</Link>}
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
        <Field
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <FormError>{submit.isError && errorMessage(submit.error, "Couldn't sign in.")}</FormError>
        <button type="submit" disabled={submit.isPending} className={primaryBtn}>
          {submit.isPending ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </AuthLayout>
  )
}
