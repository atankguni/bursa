import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { acceptInvite, errorMessage, fetchAuthOptions, fetchInvite } from '../../api'
import { useAuth } from '../../lib/auth'
import PasswordStrength from '../../components/PasswordStrength'
import { usePasswordStrength } from '../../lib/passwordStrength'
import AuthLayout, { Field, FormError, primaryBtn } from './AuthLayout'

export default function AcceptInvite() {
  const { token = '' } = useParams()
  const navigate = useNavigate()
  const { signedIn } = useAuth()
  const invite = useQuery({
    queryKey: ['auth', 'invite', token],
    queryFn: () => fetchInvite(token),
    retry: false,
  })
  const { data: options } = useQuery({
    queryKey: ['auth', 'options'],
    queryFn: fetchAuthOptions,
  })
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const strength = usePasswordStrength(password, [invite.data?.email ?? email, name])

  const submit = useMutation({
    mutationFn: () =>
      acceptInvite(token, { name, password, ...(invite.data?.email ? {} : { email }) }),
    onSuccess: (user) => {
      signedIn(user)
      navigate('/', { replace: true })
    },
  })

  if (invite.isPending)
    return <AuthLayout title="Checking your invite…">{null}</AuthLayout>
  if (invite.isError) {
    return (
      <AuthLayout
        title="Invite not valid"
        footer={
          <Link to="/" className="hover:text-ink">
            Go to sign in
          </Link>
        }
      >
        <p className="text-sm text-muted">
          {errorMessage(invite.error, 'This invite link is invalid or has expired.')}
        </p>
      </AuthLayout>
    )
  }

  const setup = invite.data.email === null
  const mismatch = confirm !== '' && confirm !== password
  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!mismatch) submit.mutate()
  }
  const minLength = options?.password_min_length ?? 12

  return (
    <AuthLayout
      title={setup ? 'Create the admin account' : 'Create your account'}
      subtitle={
        setup
          ? 'This is the first account. It can invite others and manage the server.'
          : `You were invited as ${invite.data.email}.`
      }
    >
      <form onSubmit={onSubmit} className="space-y-3">
        <Field
          label="Name"
          autoComplete="name"
          autoFocus
          required
          maxLength={80}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        {setup && (
          <Field
            label="Email"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        )}
        <Field
          label="Password"
          type="password"
          autoComplete="new-password"
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
              errorMessage(submit.error, "Couldn't create the account.")}
        </FormError>
        <button
          type="submit"
          disabled={submit.isPending || mismatch || strength?.acceptable === false}
          className={primaryBtn}
        >
          {submit.isPending ? 'Creating…' : 'Create account'}
        </button>
      </form>
    </AuthLayout>
  )
}
