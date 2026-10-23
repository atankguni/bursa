import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Lock,
  LogOut,
  Monitor,
  Moon,
  Settings as SettingsIcon,
  ShieldCheck,
  Sun,
  Users,
} from 'lucide-react'
import { useAuth } from '../lib/auth'
import { useSettings, type Theme } from '../lib/settings'

const itemCls =
  'flex w-full items-center gap-2 rounded-sm px-2.5 py-1.5 text-left text-xs text-muted transition hover:bg-panelalt hover:text-ink'

const THEMES: { value: Theme; label: string; icon: typeof Sun }[] = [
  { value: 'light', label: 'Light', icon: Sun },
  { value: 'dark', label: 'Dark', icon: Moon },
  { value: 'system', label: 'System', icon: Monitor },
]

/** Typing in a field, or a dialog is open: leave the key alone. */
function busy(e: KeyboardEvent) {
  const el = e.target instanceof Element ? e.target : null
  return (
    !!el?.closest('input, textarea, select, [contenteditable="true"]') ||
    !!document.querySelector('[aria-modal="true"]')
  )
}

/**
 * Avatar button, the hub for everything about you: who is signed in, theme,
 * settings (also with the `,` key), security, admin links and sign out.
 */
export default function AccountMenu() {
  const { user, isAdmin, signOut, lock } = useAuth()
  const { settings, update } = useSettings()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && e.target instanceof Node && !ref.current.contains(e.target))
        setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
      else if (e.key === ',' && !e.metaKey && !e.ctrlKey && !e.altKey && !busy(e)) {
        e.preventDefault()
        setOpen(false)
        void navigate('/settings')
      }
    }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [navigate])

  if (!user) return null
  const initial = (user.name || user.email).trim().charAt(0).toUpperCase()
  const close = () => setOpen(false)
  const attention = user.password_weak
    ? 'your password is weak'
    : !user.has_2fa
      ? 'two-factor authentication is off'
      : null

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label={attention ? `Account (${attention})` : 'Account'}
        aria-expanded={open}
        className="relative flex h-8 w-8 items-center justify-center rounded-sm bg-accent/15 text-xs font-semibold text-accent ring-1 ring-accent/30 transition hover:bg-accent/25"
      >
        {initial}
        {attention && (
          <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-amber-500 ring-2 ring-panel" />
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-1.5 w-64 animate-fade-in rounded-md bg-panel p-1 shadow-pop ring-1 ring-line-strong">
          <div className="border-b border-line px-2.5 py-2">
            <div className="flex items-center gap-2">
              <p className="min-w-0 flex-1 truncate text-xs font-medium text-ink">
                {user.name}
              </p>
              {isAdmin && (
                <span className="rounded-sm bg-accent/15 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-accent">
                  Admin
                </span>
              )}
            </div>
            <p className="truncate text-[11px] text-subtle">{user.email}</p>
          </div>

          <div className="flex items-center justify-between gap-2 border-b border-line px-2.5 py-2">
            <span className="text-xs text-muted">Theme</span>
            <div
              role="radiogroup"
              aria-label="Theme"
              className="inline-flex rounded-md bg-panelalt/70 p-0.5 ring-1 ring-line-strong"
            >
              {THEMES.map((t) => {
                const active = settings.theme === t.value
                return (
                  <button
                    key={t.value}
                    role="radio"
                    aria-checked={active}
                    aria-label={t.label}
                    title={t.label}
                    onClick={() => update({ theme: t.value })}
                    className={`rounded-sm p-1.5 transition ${
                      active
                        ? 'bg-panel text-ink shadow-card ring-1 ring-line-strong'
                        : 'text-muted hover:text-ink'
                    }`}
                  >
                    <t.icon size={13} />
                  </button>
                )
              })}
            </div>
          </div>

          <div className="border-b border-line py-1">
            <Link to="/settings" onClick={close} className={itemCls}>
              <SettingsIcon size={14} /> Settings
              <kbd className="ml-auto rounded-sm bg-panelalt px-1.5 font-mono text-[10px] text-subtle ring-1 ring-line">
                ,
              </kbd>
            </Link>
            <Link to="/settings/security" onClick={close} className={itemCls}>
              <ShieldCheck size={14} /> Security
              {attention && (
                <span className="ml-auto rounded-sm bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 dark:text-amber-400">
                  {user.password_weak ? 'Weak password' : '2FA off'}
                </span>
              )}
            </Link>
            {isAdmin && (
              <Link to="/settings/users" onClick={close} className={itemCls}>
                <Users size={14} /> Users &amp; invites
              </Link>
            )}
          </div>

          <div className="pt-1">
            <button onClick={() => void lock()} className={itemCls}>
              <Lock size={14} /> Lock now
            </button>
            <button onClick={() => void signOut()} className={itemCls}>
              <LogOut size={14} /> Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
