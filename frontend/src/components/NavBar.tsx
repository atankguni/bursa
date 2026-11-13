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
  `rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
    isActive ? 'bg-panelalt text-ink' : 'text-muted hover:text-ink'
  }`

/**
 * The top bar, in two layouts:
 *  - laptops and wider (lg, 1024px+): one row with the sections in it;
 *  - tablets and phones: a slim bar with a search button, sections in a bottom
 *    tab bar within thumb reach (App pads the page for it).
 */
export default function NavBar() {
  const { pathname } = useLocation()
  // Open on the page it was opened on: navigating elsewhere closes it.
  const [searchOn, setSearchOn] = useState<string | null>(null)
  const searching = searchOn === pathname

  return (
    <>
      <header className="sticky top-0 z-30 border-b border-line bg-app/80 backdrop-blur-xl backdrop-saturate-150 print:hidden">
        <div className="mx-auto flex h-14 w-full max-w-[1680px] items-center gap-3 px-4 sm:px-6 lg:gap-5 lg:px-8">
          <NavLink
            to="/"
            className="flex shrink-0 items-center gap-2"
            aria-label="Bursa home"
          >
            <span className="grid h-7 w-7 place-items-center rounded-sm bg-accent text-accent-ink shadow-card">
              <Activity size={15} strokeWidth={2.75} />
            </span>
            <span className="text-[0.9375rem] font-semibold tracking-tight">Bursa</span>
          </NavLink>

          <nav aria-label="Sections" className="hidden items-center gap-0.5 lg:flex">
            {SECTIONS.map(({ to, label, end }) => (
              <NavLink key={to} to={to} end={end} className={linkClass}>
                {label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex min-w-0 items-center gap-2">
            <div className="hidden lg:block">
              <SearchBox />
            </div>
            <div className="hidden sm:block">
              <IhsgTicker />
            </div>
            <MarketStatus />
          </div>

          <div className="flex shrink-0 items-center gap-1">
            <button
              onClick={() => setSearchOn(searching ? null : pathname)}
              aria-label={searching ? 'Close search' : 'Search ticker'}
              aria-expanded={searching}
              className="btn btn-ghost btn-icon lg:hidden"
            >
              {searching ? <X size={18} /> : <Search size={18} />}
            </button>
            <AssistantPanel />
            <AlertsBell />
            <AccountMenu />
          </div>
        </div>

        {searching && (
          <div className="px-4 pb-3 sm:px-6 lg:hidden">
            <SearchBox full autoFocus />
          </div>
        )}
      </header>

      <nav
        aria-label="Sections"
        className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-6 border-t border-line bg-panel/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden print:hidden"
      >
        {SECTIONS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex min-h-14 flex-col items-center justify-center gap-1 text-2xs font-medium transition-colors ${
                isActive ? 'text-accent' : 'text-muted hover:text-ink'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <Icon size={20} strokeWidth={isActive ? 2.25 : 1.75} />
                {label}
              </>
            )}
          </NavLink>
        ))}
      </nav>
    </>
  )
}
