import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import {
  errorMessage,
  login,
  resendTwoFactorEmail,
  verifyTwoFactor,
  type TwoFactorChallenge,
  type TwoFactorMethod,
} from '../../api'
import { useAuth } from '../../lib/auth'
import AuthLayout, { Field, FormError, primaryBtn } from './AuthLayout'

export default function Login() {
  const { signedIn } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [challenge, setChallenge] = useState<TwoFactorChallenge | null>(null)
  const submit = useMutation({
    mutationFn: () => login(email, password),
    onSuccess: (result) => {
      if (result.user) signedIn(result.user)
      else setChallenge(result.two_factor)
    },
  })

  if (challenge) {
    return (
      <SecondStep
        challenge={challenge}
        onBack={() => {
          setChallenge(null)
          setPassword('')
        }}
      />
    )
  }

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

const METHOD_LABEL: Record<TwoFactorMethod, string> = {
  totp: 'Authenticator app',
  email: 'Email code',
  recovery: 'Recovery code',
}

/** Second step: a code from the authenticator app, email, or a recovery code. */
function SecondStep({ challenge, onBack }: { challenge: TwoFactorChallenge; onBack: () => void }) {
  const { signedIn } = useAuth()
  const [method, setMethod] = useState<TwoFactorMethod>(challenge.methods[0])
  const [code, setCode] = useState('')
  const [remember, setRemember] = useState(false)
  const [emailSent, setEmailSent] = useState(challenge.email_sent)

  const verify = useMutation({
    mutationFn: () =>
      verifyTwoFactor({ token: challenge.token, method, code, remember_device: remember }),
    onSuccess: signedIn,
  })
  const resend = useMutation({
    mutationFn: () => resendTwoFactorEmail(challenge.token),
    onSuccess: () => setEmailSent(true),
  })

  const choose = (m: TwoFactorMethod) => {
    setMethod(m)
    setCode('')
    verify.reset()
    // Picking email when nothing was sent yet: send the code.
    if (m === 'email' && !emailSent && !resend.isPending) resend.mutate()
  }

  const hint =
    method === 'totp'
      ? 'Enter the 6-digit code from your authenticator app.'
      : method === 'email'
        ? emailSent
          ? `We sent a 6-digit code to ${challenge.email_hint}.`
          : `We'll send a code to ${challenge.email_hint}.`
        : 'Enter one of the recovery codes you saved. Each works once.'

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    verify.mutate()
  }

  return (
    <AuthLayout
      title="Two-factor authentication"
      subtitle={hint}
      footer={
        <button onClick={onBack} className="hover:text-ink">
          Back to sign in
        </button>
      }
    >
      <form onSubmit={onSubmit} className="space-y-3">
        <Field
          key={method}
          label={METHOD_LABEL[method]}
          autoFocus
          required
          autoComplete="one-time-code"
          inputMode={method === 'recovery' ? 'text' : 'numeric'}
          placeholder={method === 'recovery' ? 'XXXXX-XXXXX' : '123456'}
          maxLength={method === 'recovery' ? 16 : 8}
          value={code}
          onChange={(e) => setCode(e.target.value)}
        />
        <label className="flex items-center gap-2 text-xs text-muted">
          <input
            type="checkbox"
            checked={remember}
            onChange={(e) => setRemember(e.target.checked)}
            className="h-3.5 w-3.5 accent-accent"
          />
          Remember this device for 30 days
        </label>
        <FormError>
          {(verify.isError && errorMessage(verify.error, "Couldn't check the code.")) ||
            (resend.isError && errorMessage(resend.error, "Couldn't send the email."))}
        </FormError>
        <button type="submit" disabled={verify.isPending || !code.trim()} className={primaryBtn}>
          {verify.isPending ? 'Checking…' : 'Verify'}
        </button>
      </form>

      <div className="mt-4 space-y-1.5 border-t border-line pt-3 text-xs">
        {method === 'email' && (
          <button
            onClick={() => resend.mutate()}
            disabled={resend.isPending}
            className="block text-accent hover:underline disabled:opacity-50"
          >
            {resend.isPending ? 'Sending…' : emailSent ? 'Send a new code' : 'Send code'}
          </button>
        )}
        {challenge.methods
          .filter((m) => m !== method)
          .map((m) => (
            <button key={m} onClick={() => choose(m)} className="block text-muted hover:text-ink">
              Use {METHOD_LABEL[m].toLowerCase()} instead
            </button>
          ))}
      </div>
    </AuthLayout>
  )
}
