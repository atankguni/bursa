import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Copy, KeyRound, ShieldOff, Trash2, UserPlus } from 'lucide-react'
import {
  createInvite,
  createResetLink,
  deleteUser,
  errorMessage,
  fetchInvites,
  fetchUsers,
  resetTwoFactor,
  revokeInvite,
  updateUser,
  type AdminUser,
  type OneTimeLink,
  type Role,
} from '../api'
import { useAuth } from '../lib/auth'
import { fmtShortDateTime, fmtTimeAgo } from '../lib/format'

const USERS_KEY = ['admin', 'users'] as const
const INVITES_KEY = ['admin', 'invites'] as const

const inputCls =
  'rounded bg-panelalt px-3 py-1.5 text-xs text-ink ring-1 ring-line-strong outline-none focus:ring-accent'
const smallBtn =
  'inline-flex items-center gap-1 rounded px-2 py-1 text-[11px] font-medium text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink disabled:opacity-50'

/** A one-time link: shown once (only its hash is stored), with a copy button. */
function LinkNotice({
  title,
  result,
  onDismiss,
}: {
  title: string
  result: OneTimeLink
  onDismiss: () => void
}) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(result.link)
      setCopied(true)
    } catch {
      /* clipboard blocked (http): the link is selectable below */
    }
  }
  return (
    <div className="rounded bg-accent/10 p-3 text-xs ring-1 ring-accent/20">
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <span className="font-medium text-ink">{title}</span>
        <button onClick={onDismiss} className="text-[11px] text-muted hover:text-ink">
          Dismiss
        </button>
      </div>
      <p className="mb-2 text-muted">
        {result.emailed ? 'Emailed to them. ' : ''}
        Send this link yourself if needed. It works once and won&apos;t be shown again.
      </p>
      <div className="flex items-center gap-2">
        <code className="min-w-0 flex-1 select-all truncate rounded bg-panel px-2 py-1.5 font-mono text-[11px] text-ink ring-1 ring-line">
          {result.link}
        </code>
        <button onClick={() => void copy()} className={smallBtn}>
          {copied ? <Check size={12} /> : <Copy size={12} />} {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
    </div>
  )
}

const asRole = (value: string): Role => (value === 'admin' ? 'admin' : 'user')

export default function Users() {
  const qc = useQueryClient()
  const { user: me } = useAuth()
  const users = useQuery({ queryKey: USERS_KEY, queryFn: fetchUsers })
  const invites = useQuery({ queryKey: INVITES_KEY, queryFn: fetchInvites })
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<Role>('user')
  const [notice, setNotice] = useState<{ title: string; result: OneTimeLink } | null>(
    null,
  )
  const [error, setError] = useState<string | null>(null)

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: USERS_KEY })
    void qc.invalidateQueries({ queryKey: INVITES_KEY })
  }
  const onError = (fallback: string) => (e: unknown) =>
    setError(errorMessage(e, fallback))

  const invite = useMutation({
    mutationFn: () => createInvite(email, role),
    onSuccess: (result) => {
      setNotice({ title: `Invite for ${email.trim().toLowerCase()}`, result })
      setEmail('')
      setError(null)
      refresh()
    },
    onError: onError("Couldn't create the invite."),
  })
  const revoke = useMutation({ mutationFn: revokeInvite, onSuccess: refresh })
  const update = useMutation({
    mutationFn: ({
      id,
      patch,
    }: {
      id: number
      patch: Parameters<typeof updateUser>[1]
    }) => updateUser(id, patch),
    onSuccess: () => {
      setError(null)
      refresh()
    },
    onError: onError("Couldn't update the account."),
  })
  const remove = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => {
      setError(null)
      refresh()
    },
    onError: onError("Couldn't delete the account."),
  })
  const resetMfa = useMutation({
    mutationFn: resetTwoFactor,
    onSuccess: () => {
      setError(null)
      refresh()
    },
    onError: onError("Couldn't reset two-factor authentication."),
  })
  const confirmResetMfa = (u: AdminUser) => {
    if (
      window.confirm(
        `Turn off two-factor authentication for ${u.email}? Only do this if you're sure it's them (they lost their phone and recovery codes). ${u.role === 'admin' ? 'As an admin, they must set it up again at their next sign-in.' : 'They can set it up again from their account.'}`,
      )
    ) {
      resetMfa.mutate(u.id)
    }
  }
  const reset = useMutation({
    mutationFn: (u: AdminUser) => createResetLink(u.id),
    onSuccess: (result, u) => {
      setNotice({ title: `Password reset link for ${u.email}`, result })
      setError(null)
    },
    onError: onError("Couldn't create a reset link."),
  })

  const onInvite = (e: FormEvent) => {
    e.preventDefault()
    invite.mutate()
  }
  const confirmDelete = (u: AdminUser) => {
    if (
      window.confirm(
        `Delete ${u.email}? Their watchlist, portfolio and alerts are deleted too. This can't be undone.`,
      )
    ) {
      remove.mutate(u.id)
    }
  }

  // Rendered inside Settings → Users & invites, which gives the heading.
  return (
    <div className="space-y-3">
      <form onSubmit={onInvite} className="surface flex flex-wrap items-end gap-3 p-3">
        <label>
          <span className="mb-1 block text-[10px] uppercase tracking-wide text-subtle">
            Email
          </span>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="friend@example.com"
            className={`${inputCls} w-64`}
          />
        </label>
        <label>
          <span className="mb-1 block text-[10px] uppercase tracking-wide text-subtle">
            Role
          </span>
          <select
            value={role}
            onChange={(e) => setRole(asRole(e.target.value))}
            className={inputCls}
          >
            <option value="user">User</option>
            <option value="admin">Admin</option>
          </select>
        </label>
        <button
          type="submit"
          disabled={invite.isPending}
          className="inline-flex items-center gap-1.5 rounded bg-accent px-3 py-1.5 text-xs font-medium text-accent-ink transition hover:opacity-90 disabled:opacity-50"
        >
          <UserPlus size={13} /> {invite.isPending ? 'Creating…' : 'Create invite'}
        </button>
        <p className="basis-full text-[11px] text-subtle">
          Admins can also manage users, start data syncs, track symbols and see data
          health.
        </p>
      </form>

      {notice && (
        <LinkNotice
          title={notice.title}
          result={notice.result}
          onDismiss={() => setNotice(null)}
        />
      )}
      {error && (
        <p role="alert" className="text-xs text-bear">
          {error}
        </p>
      )}

      {invites.data?.length ? (
        <div className="surface overflow-hidden">
          <div className="border-b border-line px-4 py-2 text-xs font-medium">
            Pending invites
          </div>
          <table className="w-full text-xs">
            <tbody>
              {invites.data.map((i) => {
                const expired = new Date(`${i.expires_at}Z`).getTime() < Date.now()
                return (
                  <tr key={i.id} className="border-b border-line last:border-0">
                    <td className="px-4 py-2">{i.email}</td>
                    <td className="px-4 py-2 capitalize text-muted">{i.role}</td>
                    <td className="px-4 py-2 text-muted">
                      {expired ? (
                        <span className="text-bear">Expired</span>
                      ) : (
                        <>Expires {fmtShortDateTime(i.expires_at)}</>
                      )}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <button
                        onClick={() => revoke.mutate(i.id)}
                        disabled={revoke.isPending}
                        className={smallBtn}
                      >
                        Revoke
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      ) : null}

      <div className="surface overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-line text-left text-[10px] uppercase tracking-wide text-subtle">
              <th className="px-4 py-2 font-medium">Name</th>
              <th className="px-4 py-2 font-medium">Email</th>
              <th className="px-4 py-2 font-medium">Role</th>
              <th className="px-4 py-2 font-medium">2FA</th>
              <th className="px-4 py-2 font-medium">Last sign-in</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody>
            {users.isPending && (
              <tr>
                <td colSpan={7} className="px-4 py-3 text-subtle">
                  Loading…
                </td>
              </tr>
            )}
            {users.data?.map((u) => {
              const self = u.id === me?.id
              return (
                <tr key={u.id} className="border-b border-line last:border-0">
                  <td className="px-4 py-2 font-medium">
                    {u.name}
                    {self && (
                      <span className="ml-1.5 text-[10px] text-subtle">(you)</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-muted">{u.email}</td>
                  <td className="px-4 py-2">
                    <select
                      value={u.role}
                      disabled={self || update.isPending}
                      onChange={(e) =>
                        update.mutate({
                          id: u.id,
                          patch: { role: asRole(e.target.value) },
                        })
                      }
                      className={`${inputCls} py-1`}
                      aria-label={`Role of ${u.email}`}
                    >
                      <option value="user">User</option>
                      <option value="admin">Admin</option>
                    </select>
                  </td>
                  <td className="px-4 py-2">
                    {u.has_2fa ? (
                      <span className="text-bull">On</span>
                    ) : (
                      <span className={u.role === 'admin' ? 'text-bear' : 'text-subtle'}>
                        Off
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-muted">
                    {u.last_login_at ? fmtTimeAgo(u.last_login_at) : 'Never'}
                  </td>
                  <td className="px-4 py-2">
                    {u.is_active ? (
                      <span className="text-bull">Active</span>
                    ) : (
                      <span className="text-bear">Disabled</span>
                    )}
                  </td>
                  <td className="px-4 py-2">
                    {!self && (
                      <div className="flex justify-end gap-1.5">
                        <button
                          onClick={() => reset.mutate(u)}
                          disabled={reset.isPending || !u.is_active}
                          title="Create a one-time password reset link"
                          className={smallBtn}
                        >
                          <KeyRound size={12} /> Reset link
                        </button>
                        {u.has_2fa && (
                          <button
                            onClick={() => confirmResetMfa(u)}
                            disabled={resetMfa.isPending}
                            title="Turn off their 2FA (lost phone and recovery codes)"
                            className={smallBtn}
                          >
                            <ShieldOff size={12} /> Reset 2FA
                          </button>
                        )}
                        <button
                          onClick={() =>
                            update.mutate({
                              id: u.id,
                              patch: { is_active: !u.is_active },
                            })
                          }
                          disabled={update.isPending}
                          title={
                            u.is_active ? 'Block sign-in and sign out everywhere' : ''
                          }
                          className={smallBtn}
                        >
                          {u.is_active ? 'Disable' : 'Enable'}
                        </button>
                        <button
                          onClick={() => confirmDelete(u)}
                          disabled={remove.isPending}
                          aria-label={`Delete ${u.email}`}
                          className={`${smallBtn} hover:text-bear`}
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
