/** Profile: your name and email address, and your data (clear the portfolio, delete the account). */
import { useState, type FormEvent, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  cancelEmailChange,
  changeName,
  clearPortfolio,
  deleteAccount,
  errorMessage,
  fetchAuthOptions,
  fetchEmailChange,
  requestEmailChange,
} from '../../api'
import { ME_KEY, useAuth } from '../../lib/auth'
import { fmtDay } from '../../lib/format'
import { useToast } from '../../lib/toast'
import { ListRow, Rows } from './controls'

const EMAIL_CHANGE_KEY = ['account', 'email-change'] as const
const smallBtn =
  'rounded-sm px-2.5 py-1 text-xs font-medium text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink disabled:opacity-50'

function NameRow() {
  const { user } = useAuth()
  const qc = useQueryClient()
  const { toast } = useToast()
  const [draft, setDraft] = useState<string | null>(null)
  const save = useMutation({
    mutationFn: changeName,
    onSuccess: (me) => {
      qc.setQueryData(ME_KEY, me)
      setDraft(null)
      toast('Name saved')
    },
  })
  if (!user) return null
  const editing = draft !== null
  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (draft !== null && draft.trim() && draft.trim() !== user.name) save.mutate(draft)
    else setDraft(null)
  }
  return (
    <ListRow
      label="Name"
      hint={
        save.isError
          ? errorMessage(save.error, 'Could not save')
          : 'Shown in the menu and in emails'
      }
    >
      {editing ? (
        <form onSubmit={onSubmit} className="flex items-center gap-1.5">
          <input
            autoFocus
            aria-label="Name"
            maxLength={80}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === 'Escape' && (e.preventDefault(), setDraft(null))}
            className="input input-sm w-44"
          />
          <button type="submit" disabled={save.isPending} className={smallBtn}>
            Save
          </button>
        </form>
      ) : (
        <span className="flex items-center gap-2">
          <span className="text-xs text-ink">{user.name}</span>
          <button onClick={() => setDraft(user.name)} className={smallBtn}>
            Edit
          </button>
        </span>
      )}
    </ListRow>
  )
}

function EmailRow() {
  const { user } = useAuth()
  const qc = useQueryClient()
  const { toast } = useToast()
  const { data: options } = useQuery({
    queryKey: ['auth', 'options'],
    queryFn: fetchAuthOptions,
  })
  const emailReady = options?.password_reset_by_email ?? false
  const pending = useQuery({ queryKey: EMAIL_CHANGE_KEY, queryFn: fetchEmailChange })
  const [open, setOpen] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const ask = useMutation({
    mutationFn: () => requestEmailChange(email, password),
    onSuccess: (change) => {
      qc.setQueryData(EMAIL_CHANGE_KEY, change)
      setOpen(false)
      setEmail('')
      setPassword('')
      toast(`Link sent to ${change.new_email}`)
    },
  })
  const cancel = useMutation({
    mutationFn: cancelEmailChange,
    onSuccess: () => qc.setQueryData(EMAIL_CHANGE_KEY, null),
  })
  if (!user) return null
  const waiting = pending.data

  return (
    <div className="px-3.5 py-2.5">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <div className="text-xs font-medium text-ink">Email</div>
          <div className="mt-0.5 text-2xs text-subtle">
            {waiting
              ? `Waiting for you to open the link sent to ${waiting.new_email}.`
              : emailReady
                ? 'For signing in, password resets and the emails you turn on.'
                : 'Changing it needs email set up on the server; until then an admin can change it.'}
          </div>
        </div>
        <span className="flex shrink-0 items-center gap-2">
          <span className="truncate text-xs text-ink">{user.email}</span>
          {waiting ? (
            <button
              onClick={() => cancel.mutate()}
              disabled={cancel.isPending}
              className={smallBtn}
            >
              Cancel change
            </button>
          ) : (
            emailReady &&
            !open && (
              <button onClick={() => setOpen(true)} className={smallBtn}>
                Change
              </button>
            )
          )}
        </span>
      </div>
      {open && (
        <form
          onSubmit={(e) => {
            e.preventDefault()
            ask.mutate()
          }}
          className="mt-3 grid gap-2 sm:grid-cols-[1fr_1fr_auto]"
        >
          <input
            type="email"
            required
            autoFocus
            autoComplete="email"
            placeholder="New email"
            aria-label="New email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="input input-sm"
          />
          <input
            type="password"
            required
            autoComplete="current-password"
            placeholder="Your password"
            aria-label="Your password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="input input-sm"
          />
          <span className="flex gap-1.5">
            <button type="submit" disabled={ask.isPending} className="btn btn-primary">
              {ask.isPending ? 'Sending…' : 'Send link'}
            </button>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="btn btn-secondary"
            >
              Cancel
            </button>
          </span>
          <p className="text-2xs text-subtle sm:col-span-3">
            {ask.isError
              ? errorMessage(ask.error, 'Could not send the link')
              : 'We email a link to the new address; your email changes when it is opened. Your current address is told too.'}
          </p>
        </form>
      )}
    </div>
  )
}

export function ProfileSection() {
  const { user } = useAuth()
  if (!user) return null
  return (
    <Rows>
      <NameRow />
      <EmailRow />
      <ListRow label="Role">
        <span className="text-xs capitalize text-ink">{user.role}</span>
      </ListRow>
      <ListRow label="Member since">
        <span className="text-xs text-ink">{fmtDay(user.created_at)}</span>
      </ListRow>
    </Rows>
  )
}

/** A dangerous action: a button that opens a form asking for the password. */
function DangerRow({
  label,
  hint,
  action,
  confirmWord,
  run,
  done,
}: {
  label: string
  hint: ReactNode
  action: string
  confirmWord?: string
  run: (password: string) => Promise<void>
  done: () => void
}) {
  const [open, setOpen] = useState(false)
  const [password, setPassword] = useState('')
  const [typed, setTyped] = useState('')
  const go = useMutation({ mutationFn: () => run(password), onSuccess: done })
  const ready = password !== '' && (!confirmWord || typed === confirmWord)
  return (
    <div className="px-3.5 py-2.5">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <div className="text-xs font-medium text-ink">{label}</div>
          <div className="mt-0.5 text-2xs text-subtle">{hint}</div>
        </div>
        {!open && (
          <button
            onClick={() => setOpen(true)}
            className="shrink-0 rounded-sm px-2.5 py-1 text-xs font-medium text-bear ring-1 ring-bear/40 transition hover:bg-bear/10"
          >
            {action}…
          </button>
        )}
      </div>
      {open && (
        <form
          onSubmit={(e) => {
            e.preventDefault()
            if (ready) go.mutate()
          }}
          className="mt-3 space-y-2"
        >
          <div className="grid gap-2 sm:grid-cols-2">
            <input
              type="password"
              required
              autoFocus
              autoComplete="current-password"
              placeholder="Your password"
              aria-label="Your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input input-sm"
            />
            {confirmWord && (
              <input
                required
                placeholder={`Type ${confirmWord} to confirm`}
                aria-label={`Type ${confirmWord} to confirm`}
                autoComplete="off"
                value={typed}
                onChange={(e) => setTyped(e.target.value)}
                className="input input-sm"
              />
            )}
          </div>
          {go.isError && (
            <p className="text-2xs text-bear">
              {errorMessage(go.error, 'That didn’t work')}
            </p>
          )}
          <div className="flex gap-1.5">
            <button
              type="submit"
              disabled={!ready || go.isPending}
              className="btn bg-bear text-white hover:bg-bear/90 disabled:opacity-50"
            >
              {go.isPending ? 'Working…' : action}
            </button>
            <button
              type="button"
              onClick={() => {
                setOpen(false)
                setPassword('')
                setTyped('')
                go.reset()
              }}
              className="btn btn-secondary"
            >
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  )
}

export function DataSection() {
  const qc = useQueryClient()
  const { toast } = useToast()
  const { signedIn } = useAuth()
  return (
    <Rows>
      <DangerRow
        label="Clear my portfolio"
        hint="Deletes your transactions, cash movements and holding notes. Your watchlist, alerts and settings stay. This can't be undone."
        action="Clear portfolio"
        run={clearPortfolio}
        done={() => {
          void qc.invalidateQueries({ queryKey: ['portfolio'] }) // holdings, cash, notes
          toast('Portfolio cleared')
        }}
      />
      <DangerRow
        label="Delete my account"
        hint="Deletes your account and everything in it (portfolio, watchlist, alerts, chats and settings), and signs you out. This can't be undone."
        action="Delete account"
        confirmWord="DELETE"
        run={deleteAccount}
        done={() => signedIn(null)}
      />
    </Rows>
  )
}
