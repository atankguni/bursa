import { useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  Activity,
  Briefcase,
  Filter,
  Globe,
  LayoutGrid,
  List,
  Search,
  Star,
  X,
  type LucideIcon,
} from 'lucide-react'
import AccountMenu from './AccountMenu'
import AlertsBell from './AlertsBell'
import AssistantPanel from './AssistantPanel'
import IhsgTicker from './IhsgTicker'
import MarketStatus from './MarketStatus'
import SearchBox from './SearchBox'

const SECTIONS: { to: string; label: string; icon: LucideIcon; end: boolean }[] = [
  { to: '/', label: 'Home', icon: LayoutGrid, end: true },
  { to: '/watchlist', label: 'Watchlist', icon: Star, end: false },
  { to: '/portfolio', label: 'Portfolio', icon: Briefcase, end: false },
  { to: '/screener', label: 'Screener', icon: Filter, end: false },
  { to: '/market', label: 'Market', icon: Globe, end: false },
  { to: '/browse', label: 'Browse', icon: List, end: false },
]

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-1.5 rounded-sm px-2.5 py-1.5 text-xs font-medium transition ${
    isActive
      ? 'bg-panel text-accent shadow-card ring-1 ring-line-strong'
      : 'text-muted hover:bg-panelalt hover:text-ink'
  }`

function Tabs() {
  return (
    <nav
      aria-label="Sections"
      className="flex items-center gap-1 rounded-md bg-panelalt/70 p-1 ring-1 ring-line-strong"
    >
      {SECTIONS.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end} className={linkClass}>
          <Icon size={14} /> {label}
        </NavLink>
      ))}
    </nav>
  )
}

/**
 * The top bar, in three layouts:
 *  - very wide screens (2xl, 1536px+): one row;
 *  - tablets and laptops (md–2xl): sections on a second row;
 *  - phones: a slim bar with a search button; sections in a bottom tab bar.
 */
export default function NavBar() {
  const { pathname } = useLocation()
  // Open on the page it was opened on: navigating elsewhere closes it.
  const [searchOn, setSearchOn] = useState<string | null>(null)
  const searching = searchOn === pathname

  return (
    <>
      <header className="sticky top-0 z-30 border-b border-line bg-panel/80 backdrop-blur-md print:hidden">
        <div className="flex w-full items-center justify-between gap-2 px-3 py-2 sm:gap-4 sm:px-4 sm:py-2.5">
          <div className="flex min-w-0 items-center gap-2 sm:gap-4">
            <div className="flex shrink-0 items-center gap-2.5">
              <div className="rounded-md bg-accent p-1.5 text-accent-ink shadow-card sm:p-2">
                <Activity size={18} strokeWidth={2.5} />
              </div>
              <div className="hidden leading-tight sm:block">
                <h1 className="text-sm font-bold tracking-tight">Bursa</h1>
                <p className="text-[10px] font-medium uppercase tracking-wider text-subtle">
                  IDX Monitor
                </p>
              </div>
              <h1 className="text-sm font-bold tracking-tight sm:hidden">Bursa</h1>
            </div>
            <MarketStatus />
            <IhsgTicker />
            <div className="hidden md:block">
              <SearchBox />
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-1 sm:gap-2">
            <div className="hidden 2xl:block">
              <Tabs />
            </div>
            <button
              onClick={() => setSearchOn(searching ? null : pathname)}
              aria-label={searching ? 'Close search' : 'Search ticker'}
              aria-expanded={searching}
              className="rounded-sm p-2 text-muted transition hover:bg-panelalt hover:text-ink md:hidden"
            >
              {searching ? <X size={18} /> : <Search size={18} />}
            </button>
            <AssistantPanel />
            <AlertsBell />
            <AccountMenu />
          </div>
        </div>

        {searching && (
          <div className="px-3 pb-2 md:hidden">
            <SearchBox full autoFocus />
          </div>
        )}

        <div className="hidden px-4 pb-2 md:block 2xl:hidden">
          <Tabs />
        </div>
      </header>

      {/* Phones: sections within thumb reach. Shell pads the page for it. */}
      <nav
        aria-label="Sections"
        className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-6 border-t border-line bg-panel/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-md md:hidden print:hidden"
      >
        {SECTIONS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex min-h-14 flex-col items-center justify-center gap-0.5 text-[10px] font-medium transition ${
                isActive ? 'text-accent' : 'text-muted hover:text-ink'
              }`
            }
          >
            <Icon size={20} />
            {label}
          </NavLink>
        ))}
      </nav>
    </>
  )
}
