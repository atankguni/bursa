import { NavLink } from 'react-router-dom'
import { Activity, LayoutGrid, Star } from 'lucide-react'
import MarketStatus from './MarketStatus'
import SettingsMenu from './SettingsMenu'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition ${
    isActive
      ? 'bg-panel text-ink shadow-card ring-1 ring-line'
      : 'text-muted hover:bg-panelalt hover:text-ink'
  }`

/** Full-width, compact top bar: brand, navigation, market status, settings. */
export default function NavBar() {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-panel/80 backdrop-blur-md">
      <div className="flex w-full items-center justify-between gap-4 px-4 py-2.5">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2.5">
            <div className="rounded-xl bg-gradient-to-br from-bull to-emerald-600 p-2 text-white shadow-card">
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
        </div>

        <div className="flex items-center gap-2">
          <nav className="flex items-center gap-1 rounded-xl bg-panelalt/70 p-1 ring-1 ring-line">
            <NavLink to="/" end className={linkClass}>
              <LayoutGrid size={14} /> Home
            </NavLink>
            <NavLink to="/watchlist" className={linkClass}>
              <Star size={14} /> Watchlist
            </NavLink>
          </nav>
          <SettingsMenu />
        </div>
      </div>
    </header>
  )
}
