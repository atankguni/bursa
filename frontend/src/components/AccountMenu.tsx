import { useEffect, useRef, useState, type FormEvent } from 'react'
import { createPortal } from 'react-dom'
import { Link } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { KeyRound, LogOut, Users, X } from 'lucide-react'
import { changePassword, errorMessage } from '../api'
import { useAuth } from '../lib/auth'
import { Field, FormError } from '../pages/auth/AuthLayout'

const itemCls =
  'flex w-full items-center gap-2 rounded px-2.5 py-1.5 text-left text-xs text-muted transition hover:bg-panelalt hover:text-ink'

/** Avatar button: who is signed in, password, admin links, sign out. */
export default function AccountMenu() {
  const { user, isAdmin, signOut } = useAuth()
  const [open, setOpen] = useState(false)
  const [changing, setChanging] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  if (!user) return null
  const initial = (user.name || user.email).trim().charAt(0).toUpperCase()

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label="Account"
        aria-expanded={open}
        className="flex h-8 w-8 items-center justify-center rounded-full bg-accent/15 text-xs font-semibold text-accent ring-1 ring-accent/30 transition hover:bg-accent/25"
      >
        {initial}
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-1.5 w-60 animate-fade-in rounded-md bg-panel p-1 shadow-pop ring-1 ring-line-strong">
          <div className="border-b border-line px-2.5 py-2">
            <p className="truncate text-xs font-medium text-ink">{user.name}</p>
            <p className="truncate text-[11px] text-subtle">{user.email}</p>
            {isAdmin && (
              <span className="mt-1 inline-block rounded bg-accent/15 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-accent">
                Admin
              </span>
            )}
          </div>
          <div className="pt-1">
            {isAdmin && (
              <Link to="/admin/users" onClick={() => setOpen(false)} className={itemCls}>
                <Users size={14} /> Users &amp; invites
              </Link>
            )}
            <button
              onClick={() => {
                setOpen(false)
                setChanging(true)
              }}
              className={itemCls}
            >
              <KeyRound size={14} /> Change password
            </button>
            <button onClick={() => void signOut()} className={itemCls}>
              <LogOut size={14} /> Sign out
            </button>
          </div>
        </div>
      )}
      {changing && <ChangePasswordModal onClose={() => setChanging(false)} />}
    </div>
  )
}

function ChangePasswordModal({ onClose }: { onClose: () => void }) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const save = useMutation({ mutationFn: () => changePassword(current, next) })
  const mismatch = confirm !== '' && confirm !== next

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (!mismatch) save.mutate()
  }

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-sm animate-fade-in rounded-md bg-panel p-6 shadow-pop ring-1 ring-line"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Change password</h2>
          <button
            onClick={onClose}
            className="rounded p-1.5 text-muted transition hover:bg-panelalt hover:text-ink"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>
        {save.isSuccess ? (
          <div className="space-y-4">
            <p className="text-sm text-muted">
              Password changed. Your other browsers and devices were signed out.
            </p>
            <div className="flex justify-end">
              <button
                onClick={onClose}
                className="rounded bg-accent px-3 py-1.5 text-xs font-medium text-accent-ink transition hover:opacity-90"
              >
                Done
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="space-y-3">
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
                : save.isError && errorMessage(save.error, "Couldn't change the password.")}
            </FormError>
            <div className="flex justify-end gap-2 pt-1">
              <button
                type="button"
                onClick={onClose}
                className="rounded px-3 py-1.5 text-xs text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={save.isPending || mismatch}
                className="rounded bg-accent px-3 py-1.5 text-xs font-medium text-accent-ink transition hover:opacity-90 disabled:opacity-50"
              >
                {save.isPending ? 'Saving…' : 'Change password'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>,
    document.body,
  )
}
