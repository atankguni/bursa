import { NavLink } from 'react-router-dom'
import { Activity, Briefcase, Filter, Globe, LayoutGrid, List, Star } from 'lucide-react'
import AlertsBell from './AlertsBell'
import AssistantPanel from './AssistantPanel'
import IhsgTicker from './IhsgTicker'
import MarketStatus from './MarketStatus'
import SearchBox from './SearchBox'
import SettingsMenu from './SettingsMenu'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-1.5 rounded px-2.5 py-1.5 text-xs font-medium transition ${
    isActive
      ? 'bg-panel text-accent shadow-card ring-1 ring-line-strong'
      : 'text-muted hover:bg-panelalt hover:text-ink'
  }`

/** Full-width, compact top bar: brand, navigation, market status, settings. */
export default function NavBar() {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-panel/80 backdrop-blur-md">
      <div className="flex w-full items-center justify-between gap-4 px-4 py-2.5">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2.5">
            <div className="rounded-md bg-accent p-2 text-accent-ink shadow-card">
              <Activity size={18} strokeWidth={2.5} />
            </div>
            <div className="leading-tight">
              <h1 className="text-sm font-bold tracking-tight">Bursa</h1>
              <p className="text-[10px] font-medium uppercase tracking-wider text-subtle">
                IDX Monitor
              </p>
            </div>
          </div>
          <MarketStatus />
          <IhsgTicker />
          <SearchBox />
        </div>

        <div className="flex items-center gap-2">
          <nav className="flex items-center gap-1 rounded-md bg-panelalt/70 p-1 ring-1 ring-line-strong">
            <NavLink to="/" end className={linkClass}>
              <LayoutGrid size={14} /> Home
            </NavLink>
            <NavLink to="/watchlist" className={linkClass}>
              <Star size={14} /> Watchlist
            </NavLink>
            <NavLink to="/portfolio" className={linkClass}>
              <Briefcase size={14} /> Portfolio
            </NavLink>
            <NavLink to="/screener" className={linkClass}>
              <Filter size={14} /> Screener
            </NavLink>
            <NavLink to="/market" className={linkClass}>
              <Globe size={14} /> Market
            </NavLink>
            <NavLink to="/browse" className={linkClass}>
              <List size={14} /> Browse
            </NavLink>
          </nav>
          <AssistantPanel />
          <AlertsBell />
          <SettingsMenu />
        </div>
      </div>
    </header>
  )
}
