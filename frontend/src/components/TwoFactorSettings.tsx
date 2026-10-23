import { useState, type FormEvent, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Check,
  Copy,
  Download,
  KeyRound,
  Mail,
  MonitorSmartphone,
  Smartphone,
} from 'lucide-react'
import {
  confirmEmail,
  confirmTotp,
  disableTwoFactor,
  errorMessage,
  fetchTwoFactorStatus,
  forgetTrustedDevices,
  regenerateRecoveryCodes,
  startEmailSetup,
  startTotpSetup,
  type TotpSetup,
} from '../api'
import { ME_KEY } from '../lib/auth'

export const TWO_FACTOR_KEY = ['auth', '2fa'] as const

const inputCls =
  'w-full rounded-sm bg-panelalt px-3 py-2 text-sm text-ink ring-1 ring-line-strong outline-hidden focus:ring-accent'
const primaryBtn =
  'rounded-sm bg-accent px-3 py-1.5 text-xs font-medium text-accent-ink transition hover:opacity-90 disabled:opacity-50'
const secondaryBtn =
  'rounded-sm px-3 py-1.5 text-xs font-medium text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink disabled:opacity-50'

function Card({
  icon,
  title,
  status,
  children,
}: {
  icon: ReactNode
  title: string
  status?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="rounded-md bg-panelalt/40 p-4 ring-1 ring-line">
      <div className="mb-2 flex items-center gap-2">
        <span className="text-accent">{icon}</span>
        <h3 className="text-sm font-semibold">{title}</h3>
        {status && <span className="ml-auto text-xs">{status}</span>}
      </div>
      <div className="space-y-3 text-xs text-muted">{children}</div>
    </section>
  )
}

const On = () => <span className="font-medium text-bull">On</span>
const Off = () => <span className="text-subtle">Off</span>

function ErrorText({ error, fallback }: { error: unknown; fallback: string }) {
  return error ? (
    <p role="alert" className="text-xs text-bear">
      {errorMessage(error, fallback)}
    </p>
  ) : null
}

/** Asks for the password before something that weakens or resets 2FA. */
function PasswordConfirm({
  label,
  danger,
  pending,
  error,
  onConfirm,
  onCancel,
}: {
  label: string
  danger?: boolean
  pending: boolean
  error: unknown
  onConfirm: (password: string) => void
  onCancel: () => void
}) {
  const [password, setPassword] = useState('')
  const submit = (e: FormEvent) => {
    e.preventDefault()
    onConfirm(password)
  }
  return (
    <form onSubmit={submit} className="space-y-2">
      <label className="block">
        <span className="mb-1 block">Confirm with your password</span>
        <input
          type="password"
          autoComplete="current-password"
          autoFocus
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className={inputCls}
        />
      </label>
      <ErrorText error={error} fallback="Something went wrong." />
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={pending || !password}
          className={danger ? `${secondaryBtn} text-bear ring-bear/40` : primaryBtn}
        >
          {pending ? 'Working…' : label}
        </button>
        <button type="button" onClick={onCancel} className={secondaryBtn}>
          Cancel
        </button>
      </div>
    </form>
  )
}

function CodeForm({
  label,
  pending,
  error,
  onSubmit,
}: {
  label: string
  pending: boolean
  error: unknown
  onSubmit: (code: string) => void
}) {
  const [code, setCode] = useState('')
  const submit = (e: FormEvent) => {
    e.preventDefault()
    onSubmit(code)
  }
  return (
    <form onSubmit={submit} className="space-y-2">
      <label className="block">
        <span className="mb-1 block">{label}</span>
        <input
          autoFocus
          required
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={8}
          placeholder="123456"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          className={`${inputCls} max-w-[10rem] tracking-widest`}
        />
      </label>
      <ErrorText error={error} fallback="Couldn't check the code." />
      <button type="submit" disabled={pending || !code.trim()} className={primaryBtn}>
        {pending ? 'Checking…' : 'Turn on'}
      </button>
    </form>
  )
}

/** Shown once after they are created: copy, download, then confirm. */
export function RecoveryCodes({
  codes,
  onDone,
}: {
  codes: string[]
  onDone: () => void
}) {
  const [copied, setCopied] = useState(false)
  const text = `Bursa recovery codes (each works once)\n\n${codes.join('\n')}\n`
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
    } catch {
      /* clipboard blocked: the codes can be selected or downloaded */
    }
  }
  const download = () => {
    const url = URL.createObjectURL(new Blob([text], { type: 'text/plain' }))
    const a = document.createElement('a')
    a.href = url
    a.download = 'bursa-recovery-codes.txt'
    a.click()
    URL.revokeObjectURL(url)
  }
  return (
    <div className="rounded-md bg-accent/10 p-4 text-xs ring-1 ring-accent/25">
      <p className="mb-1 text-sm font-semibold text-ink">Save your recovery codes</p>
      <p className="mb-3 text-muted">
        If you lose your phone or can&apos;t get email, each code signs you in once. Keep
        them somewhere safe, like a password manager. They won&apos;t be shown again.
      </p>
      <ul className="mb-3 grid select-all grid-cols-2 gap-x-6 gap-y-1 font-mono text-sm text-ink">
        {codes.map((c) => (
          <li key={c}>{c}</li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => void copy()}
          className={`${secondaryBtn} inline-flex items-center gap-1.5`}
        >
          {copied ? <Check size={13} /> : <Copy size={13} />} {copied ? 'Copied' : 'Copy'}
        </button>
        <button
          onClick={download}
          className={`${secondaryBtn} inline-flex items-center gap-1.5`}
        >
          <Download size={13} /> Download
        </button>
        <button onClick={onDone} className={primaryBtn}>
          I&apos;ve saved them
        </button>
      </div>
    </div>
  )
}

/** Turn methods on and off, recovery codes, remembered devices. */
export default function TwoFactorSettings() {
  const qc = useQueryClient()
  const { data: status, isPending } = useQuery({
    queryKey: TWO_FACTOR_KEY,
    queryFn: fetchTwoFactorStatus,
  })
  const [codes, setCodes] = useState<string[] | null>(null)
  const [totpSetup, setTotpSetup] = useState<TotpSetup | null>(null)
  const [emailCodeSent, setEmailCodeSent] = useState(false)
  const [confirming, setConfirming] = useState<'totp' | 'email' | 'codes' | null>(null)

  const refreshStatus = () => qc.invalidateQueries({ queryKey: TWO_FACTOR_KEY })
  // /me decides whether an admin is still held at the setup screen. With new
  // recovery codes it waits until they're saved, so they don't vanish with it.
  const refreshMe = () => qc.invalidateQueries({ queryKey: ME_KEY })
  const enabled = (newCodes: string[] | null) => {
    void refreshStatus()
    if (newCodes) setCodes(newCodes)
    else void refreshMe()
  }

  const beginTotp = useMutation({ mutationFn: startTotpSetup, onSuccess: setTotpSetup })
  const finishTotp = useMutation({
    mutationFn: confirmTotp,
    onSuccess: (newCodes) => {
      setTotpSetup(null)
      enabled(newCodes)
    },
  })
  const beginEmail = useMutation({
    mutationFn: startEmailSetup,
    onSuccess: () => setEmailCodeSent(true),
  })
  const finishEmail = useMutation({
    mutationFn: confirmEmail,
    onSuccess: (newCodes) => {
      setEmailCodeSent(false)
      enabled(newCodes)
    },
  })
  const disable = useMutation({
    mutationFn: ({ method, password }: { method: 'totp' | 'email'; password: string }) =>
      disableTwoFactor(method, password),
    onSuccess: () => {
      setConfirming(null)
      void refreshStatus()
      void refreshMe()
    },
  })
  const regenerate = useMutation({
    mutationFn: regenerateRecoveryCodes,
    onSuccess: (newCodes) => {
      setConfirming(null)
      setCodes(newCodes)
      void refreshStatus()
    },
  })
  const forget = useMutation({
    mutationFn: forgetTrustedDevices,
    onSuccess: refreshStatus,
  })

  if (isPending || !status) return <p className="text-xs text-subtle">Loading…</p>

  if (codes) {
    return (
      <RecoveryCodes
        codes={codes}
        onDone={() => {
          setCodes(null)
          void refreshMe()
        }}
      />
    )
  }

  const anyOn = status.totp || status.email
  const onlyMethod = (m: 'totp' | 'email') =>
    status.required && (m === 'totp' ? !status.email : !status.totp)

  return (
    <div className="space-y-3">
      <Card
        icon={<Smartphone size={16} />}
        title="Authenticator app"
        status={status.totp ? <On /> : <Off />}
      >
        <p>
          Codes from an app such as Google Authenticator, Microsoft Authenticator,
          1Password or Bitwarden. Works offline and doesn&apos;t depend on email.
          {!status.email && !status.totp && ' Recommended.'}
        </p>
        {status.totp ? (
          confirming === 'totp' ? (
            <PasswordConfirm
              label="Remove authenticator app"
              danger
              pending={disable.isPending}
              error={disable.error}
              onConfirm={(password) => disable.mutate({ method: 'totp', password })}
              onCancel={() => setConfirming(null)}
            />
          ) : onlyMethod('totp') ? (
            <p className="text-subtle">Admins must keep two-factor authentication on.</p>
          ) : (
            <button onClick={() => setConfirming('totp')} className={secondaryBtn}>
              Remove
            </button>
          )
        ) : totpSetup ? (
          <div className="space-y-3">
            <ol className="list-decimal space-y-1 pl-4">
              <li>Open your authenticator app and add an account.</li>
              <li>Scan this QR code, or enter the key below.</li>
              <li>Type the 6-digit code the app shows.</li>
            </ol>
            <div className="flex flex-wrap items-center gap-4">
              {/* Server-made SVG (segno): no image is fetched from elsewhere. */}
              <div
                className="rounded-sm bg-white p-1 [&>svg]:h-40 [&>svg]:w-40"
                aria-label="QR code for your authenticator app"
                dangerouslySetInnerHTML={{ __html: totpSetup.qr_svg }}
              />
              <div className="min-w-0 space-y-1">
                <p>Key (if you can&apos;t scan):</p>
                <code className="block select-all break-all rounded-sm bg-panel px-2 py-1 font-mono text-[11px] text-ink ring-1 ring-line">
                  {totpSetup.secret.match(/.{1,4}/g)?.join(' ')}
                </code>
                <a
                  href={totpSetup.uri}
                  className="inline-block text-accent hover:underline"
                >
                  Open in authenticator app (on this phone)
                </a>
              </div>
            </div>
            <CodeForm
              label="Code from the app"
              pending={finishTotp.isPending}
              error={finishTotp.error}
              onSubmit={(code) => finishTotp.mutate(code)}
            />
          </div>
        ) : (
          <>
            <ErrorText error={beginTotp.error} fallback="Couldn't start the setup." />
            <button
              onClick={() => beginTotp.mutate()}
              disabled={beginTotp.isPending}
              className={primaryBtn}
            >
              Set up authenticator app
            </button>
          </>
        )}
      </Card>

      <Card
        icon={<Mail size={16} />}
        title="Email code"
        status={status.email ? <On /> : <Off />}
      >
        <p>A 6-digit code sent to your account email at each sign-in.</p>
        {status.email ? (
          confirming === 'email' ? (
            <PasswordConfirm
              label="Turn off email codes"
              danger
              pending={disable.isPending}
              error={disable.error}
              onConfirm={(password) => disable.mutate({ method: 'email', password })}
              onCancel={() => setConfirming(null)}
            />
          ) : onlyMethod('email') ? (
            <p className="text-subtle">Admins must keep two-factor authentication on.</p>
          ) : (
            <button onClick={() => setConfirming('email')} className={secondaryBtn}>
              Turn off
            </button>
          )
        ) : !status.email_available ? (
          <p className="text-subtle">
            Not available: email isn&apos;t set up on this server. Use an authenticator
            app.
          </p>
        ) : emailCodeSent ? (
          <>
            <p>We sent a code to your email.</p>
            <CodeForm
              label="Code from the email"
              pending={finishEmail.isPending}
              error={finishEmail.error}
              onSubmit={(code) => finishEmail.mutate(code)}
            />
          </>
        ) : (
          <>
            <ErrorText error={beginEmail.error} fallback="Couldn't send the email." />
            <button
              onClick={() => beginEmail.mutate()}
              disabled={beginEmail.isPending}
              className={primaryBtn}
            >
              {beginEmail.isPending ? 'Sending…' : 'Send a code to my email'}
            </button>
          </>
        )}
      </Card>

      {anyOn && (
        <Card
          icon={<KeyRound size={16} />}
          title="Recovery codes"
          status={
            <span
              className={status.recovery_codes_left <= 2 ? 'text-bear' : 'text-muted'}
            >
              {status.recovery_codes_left} left
            </span>
          }
        >
          <p>Single-use backups for when you can&apos;t use your phone or email.</p>
          {confirming === 'codes' ? (
            <PasswordConfirm
              label="Create new codes"
              pending={regenerate.isPending}
              error={regenerate.error}
              onConfirm={(password) => regenerate.mutate(password)}
              onCancel={() => setConfirming(null)}
            />
          ) : (
            <button onClick={() => setConfirming('codes')} className={secondaryBtn}>
              Create new codes (old ones stop working)
            </button>
          )}
        </Card>
      )}

      {anyOn && (
        <Card icon={<MonitorSmartphone size={16} />} title="Remembered devices">
          <p>
            {status.trusted_devices === 0
              ? 'No device skips the code right now.'
              : `${status.trusted_devices} device${status.trusted_devices === 1 ? '' : 's'} can sign in without a code for up to 30 days.`}
          </p>
          {status.trusted_devices > 0 && (
            <button
              onClick={() => forget.mutate()}
              disabled={forget.isPending}
              className={secondaryBtn}
            >
              Forget all devices
            </button>
          )}
        </Card>
      )}
    </div>
  )
}
