import { Navigate, NavLink, useParams } from 'react-router-dom'
import {
  Columns3,
  Palette,
  RotateCcw,
  Settings as SettingsIcon,
  ShieldCheck,
  SlidersHorizontal,
  TrendingUp,
  Users as UsersIcon,
} from 'lucide-react'
import { useAuth } from '../lib/auth'
import { useSettings } from '../lib/settings'
import AppearanceSection from './settings/AppearanceSection'
import DisplaySection from './settings/DisplaySection'
import InvestingSection from './settings/InvestingSection'
import TablesSection from './settings/TablesSection'
import Security from './Security'
import Users from './Users'

const SCOPE_LABEL = {
  account: {
    label: 'Your account',
    hint: 'Saved to your account: the same on all your devices',
  },
  device: {
    label: 'This device',
    hint: 'Saved in this browser only, so each device can differ',
  },
}

/** Appearance, display and tables share one reset (lib/settings). */
function ResetSettings() {
  const { reset } = useSettings()
  const onReset = () => {
    if (
      window.confirm('Reset appearance, display and table settings to their defaults?')
    ) {
      reset()
    }
  }
  return (
    <button
      onClick={onReset}
      className="inline-flex items-center gap-1.5 rounded px-3 py-1.5 text-xs font-medium text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink"
    >
      <RotateCcw size={13} /> Reset appearance, display &amp; tables
    </button>
  )
}

type SectionId = 'investing' | 'appearance' | 'display' | 'tables' | 'security' | 'users'

const SECTIONS: {
  id: SectionId
  label: string
  icon: typeof Palette
  description: string
  scope?: 'account' | 'device'
  adminOnly?: boolean
  wide?: boolean
}[] = [
  {
    id: 'investing',
    label: 'Investing',
    icon: TrendingUp,
    description: 'How signals are scored for you, and what the assistant may see.',
    scope: 'account',
  },
  {
    id: 'appearance',
    label: 'Appearance',
    icon: Palette,
    description: 'Theme, colours and spacing.',
    scope: 'device',
  },
  {
    id: 'display',
    label: 'Display',
    icon: SlidersHorizontal,
    description: 'Numbers, charts and refreshing.',
    scope: 'account',
  },
  {
    id: 'tables',
    label: 'Tables & indices',
    icon: Columns3,
    description: 'Which indices and columns you see first.',
    scope: 'account',
  },
  {
    id: 'security',
    label: 'Security',
    icon: ShieldCheck,
    description: 'Password, two-factor authentication and remembered devices.',
  },
  {
    id: 'users',
    label: 'Users & invites',
    icon: UsersIcon,
    description: 'Invite-only: people join through a link you create here.',
    adminOnly: true,
    wide: true,
  },
]

const navCls = ({ isActive }: { isActive: boolean }) =>
  `flex shrink-0 items-center gap-2 whitespace-nowrap rounded px-2.5 py-1.5 text-xs font-medium transition ${
    isActive
      ? 'bg-panel text-accent shadow-card ring-1 ring-line-strong'
      : 'text-muted hover:bg-panelalt hover:text-ink'
  }`

// --------------------------------------------------------------------------- //
// Settings page: /settings/:section
// --------------------------------------------------------------------------- //

export default function Settings() {
  const { section: id } = useParams()
  const { user, isAdmin } = useAuth()
  const sections = SECTIONS.filter((s) => !s.adminOnly || isAdmin)
  const section = sections.find((s) => s.id === id)
  if (!section) return <Navigate to="/settings/investing" replace />

  return (
    <main className="w-full animate-fade-in px-4 py-4">
      <div className="mb-4 flex items-center gap-2">
        <SettingsIcon size={16} className="text-accent" />
        <h2 className="text-sm font-semibold tracking-tight">Settings</h2>
        <p className="text-[11px] text-subtle">Changes apply instantly</p>
      </div>

      <div className="flex flex-col gap-4 md:flex-row md:items-start">
        {/* Side menu on wide screens, a scrolling row of tabs on phones. */}
        <nav
          aria-label="Settings sections"
          className="-mx-4 flex gap-1 overflow-x-auto px-4 md:sticky md:top-20 md:mx-0 md:w-48 md:shrink-0 md:flex-col md:px-0"
        >
          {sections.map((s) => (
            <NavLink key={s.id} to={`/settings/${s.id}`} className={navCls}>
              <s.icon size={14} /> {s.label}
              {s.id === 'security' && (user?.password_weak || !user?.has_2fa) && (
                <span className="ml-auto rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 dark:text-amber-400">
                  {user?.password_weak ? 'Weak password' : '2FA off'}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        <section
          className={`min-w-0 flex-1 space-y-3 ${section.wide ? '' : 'max-w-3xl'}`}
        >
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold">{section.label}</h3>
              {section.scope && (
                <span
                  title={SCOPE_LABEL[section.scope].hint}
                  className="rounded bg-panelalt px-1.5 py-0.5 text-[10px] font-medium text-subtle ring-1 ring-line"
                >
                  {SCOPE_LABEL[section.scope].label}
                </span>
              )}
            </div>
            <p className="mt-0.5 text-xs text-muted">{section.description}</p>
          </div>

          {section.id === 'investing' && <InvestingSection />}
          {section.id === 'appearance' && <AppearanceSection />}
          {section.id === 'display' && <DisplaySection />}
          {section.id === 'tables' && <TablesSection />}
          {section.id === 'security' && <Security />}
          {section.id === 'users' && <Users />}

          {(section.id === 'appearance' ||
            section.id === 'display' ||
            section.id === 'tables') && (
            <div className="pt-1">
              <ResetSettings />
            </div>
          )}
        </section>
      </div>
    </main>
  )
}
