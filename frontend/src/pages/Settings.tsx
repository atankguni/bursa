import { useState } from 'react'
import { Navigate, NavLink, useNavigate, useParams } from 'react-router-dom'
import {
  Bell,
  Columns3,
  Database,
  Keyboard,
  Palette,
  RotateCcw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  TrendingUp,
  UserRound,
  Users as UsersIcon,
} from 'lucide-react'
import { useAuth } from '../lib/auth'
import { useSettings } from '../lib/settings'
import AppearanceSection from './settings/AppearanceSection'
import DisplaySection from './settings/DisplaySection'
import InvestingSection from './settings/InvestingSection'
import NotificationsSection from './settings/NotificationsSection'
import { DataSection, ProfileSection } from './settings/ProfileSection'
import ShortcutsSection from './settings/ShortcutsSection'
import TablesSection from './settings/TablesSection'
import Security from './Security'
import Users from './Users'
import { clearStoredViews } from '../lib/storedState'

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
  const { user } = useAuth()
  const onReset = () => {
    if (
      window.confirm(
        'Reset appearance, display and table settings to their defaults, and forget the sorting, filters and chart choices each page remembers?',
      )
    ) {
      reset()
      clearStoredViews(user?.id)
      window.location.reload() // pages read their remembered choices when they open
    }
  }
  return (
    <button onClick={onReset} className="btn btn-secondary">
      <RotateCcw size={13} /> Reset appearance, display &amp; tables
    </button>
  )
}

type SectionId =
  | 'profile'
  | 'investing'
  | 'notifications'
  | 'appearance'
  | 'display'
  | 'tables'
  | 'security'
  | 'data'
  | 'shortcuts'
  | 'users'

const SECTIONS: {
  id: SectionId
  label: string
  icon: typeof Palette
  description: string
  /** More words the settings search finds this section by. */
  keywords: string
  scope?: 'account' | 'device'
  adminOnly?: boolean
  wide?: boolean
}[] = [
  {
    id: 'profile',
    label: 'Profile',
    icon: UserRound,
    description: 'Your name and email address.',
    keywords: 'name email address role member joined account',
  },
  {
    id: 'investing',
    label: 'Investing',
    icon: TrendingUp,
    description:
      'How signals are scored for you, what the assistant may see, and your portfolio’s benchmark, limits and costs.',
    keywords:
      'style investor trader assistant ai gemini chats benchmark ihsg lq45 jii compare risk limit concentration sector stock lots shares trade unit fees broker tax dividend costs',
    scope: 'account',
  },
  {
    id: 'notifications',
    label: 'Notifications',
    icon: Bell,
    description: 'Emails Bursa sends you.',
    keywords: 'email daily summary digest alert emails quiet hours night',
    scope: 'account',
  },
  {
    id: 'appearance',
    label: 'Appearance',
    icon: Palette,
    description: 'Theme, colours and spacing.',
    keywords: 'theme dark light colour color accent contrast density spacing font',
    scope: 'device',
  },
  {
    id: 'display',
    label: 'Display',
    icon: SlidersHorizontal,
    description: 'Numbers, dates, the start page, charts and refreshing.',
    keywords:
      'number format compact full locale indonesian comma dot date start page home hide amounts privacy chart candle line refresh colorize',
    scope: 'account',
  },
  {
    id: 'tables',
    label: 'Tables & indices',
    icon: Columns3,
    description: 'Which indices and columns you see first.',
    keywords: 'index indices columns table lq45 idx30',
    scope: 'account',
  },
  {
    id: 'security',
    label: 'Security',
    icon: ShieldCheck,
    description: 'Password, two-factor authentication, signed-in devices and activity.',
    keywords:
      'password 2fa two-factor authenticator recovery codes devices sessions sign out activity lock idle',
  },
  {
    id: 'data',
    label: 'Your data',
    icon: Database,
    description: 'Start your portfolio over, or delete your account.',
    keywords: 'clear reset portfolio transactions delete account remove',
  },
  {
    id: 'shortcuts',
    label: 'Shortcuts',
    icon: Keyboard,
    description: 'Keys that get you around faster.',
    keywords: 'keyboard keys hotkeys shortcuts search',
  },
  {
    id: 'users',
    label: 'Users & invites',
    icon: UsersIcon,
    description: 'Invite-only: people join through a link you create here.',
    keywords: 'invite users people family admin role disable',
    adminOnly: true,
    wide: true,
  },
]

const navCls = ({ isActive }: { isActive: boolean }) =>
  `flex shrink-0 items-center gap-2 whitespace-nowrap rounded-sm px-2.5 py-1.5 text-xs font-medium transition ${
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
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const sections = SECTIONS.filter((s) => !s.adminOnly || isAdmin)
  const section = sections.find((s) => s.id === id)
  if (!section) return <Navigate to="/settings/profile" replace />
  const words = query.toLowerCase().split(/\s+/).filter(Boolean)
  const shown = sections.filter((s) => {
    const text = `${s.label} ${s.description} ${s.keywords}`.toLowerCase()
    return words.every((w) => text.includes(w))
  })

  return (
    <main className="page">
      <div className="mb-5 lg:mb-6">
        <h2 className="page-title">Settings</h2>
        <p className="page-sub">Changes apply instantly</p>
      </div>

      <div className="flex flex-col gap-4 md:flex-row md:items-start">
        {/* Side menu on wide screens, a scrolling row of tabs on phones. */}
        <nav
          aria-label="Settings sections"
          className="-mx-4 flex gap-1 relative overflow-x-auto px-4 md:sticky md:top-20 md:mx-0 md:w-48 md:shrink-0 md:flex-col md:px-0"
        >
          <label className="relative hidden shrink-0 md:block">
            <Search
              size={13}
              className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-subtle"
            />
            <input
              type="search"
              aria-label="Search settings"
              placeholder="Search settings"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && shown[0])
                  void navigate(`/settings/${shown[0].id}`)
                if (e.key === 'Escape' && query) {
                  e.preventDefault()
                  setQuery('')
                }
              }}
              className="input input-sm mb-1 w-full pl-7"
            />
          </label>
          {shown.length === 0 && (
            <p className="hidden px-2.5 py-1.5 text-2xs text-subtle md:block">
              No matches
            </p>
          )}
          {(words.length ? shown : sections).map((s) => (
            <NavLink key={s.id} to={`/settings/${s.id}`} className={navCls}>
              <s.icon size={14} /> {s.label}
              {s.id === 'security' && (user?.password_weak || !user?.has_2fa) && (
                <span className="ml-auto rounded-sm bg-amber-500/10 px-1.5 py-0.5 text-2xs font-medium text-amber-700 dark:text-amber-400">
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
                  className="rounded-sm bg-panelalt px-1.5 py-0.5 text-2xs font-medium text-subtle ring-1 ring-line"
                >
                  {SCOPE_LABEL[section.scope].label}
                </span>
              )}
            </div>
            <p className="mt-0.5 text-xs text-muted">{section.description}</p>
          </div>

          {section.id === 'profile' && <ProfileSection />}
          {section.id === 'investing' && <InvestingSection />}
          {section.id === 'notifications' && <NotificationsSection />}
          {section.id === 'appearance' && <AppearanceSection />}
          {section.id === 'display' && <DisplaySection />}
          {section.id === 'tables' && <TablesSection />}
          {section.id === 'security' && <Security />}
          {section.id === 'data' && <DataSection />}
          {section.id === 'shortcuts' && <ShortcutsSection />}
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
