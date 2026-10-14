import { NavLink } from 'react-router-dom'
import { Activity, LayoutGrid, Star } from 'lucide-react'
import ThemeToggle from './ThemeToggle'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition ${
    isActive ? 'bg-active text-ink' : 'text-muted hover:bg-panelalt hover:text-ink'
  }`

// Full-width, compact top bar: brand, navigation, theme switcher.
export default function NavBar() {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-panel/90 backdrop-blur">
      <div className="flex w-full items-center justify-between gap-4 px-4 py-2">
        <div className="flex items-center gap-2">
          <div className="rounded-md bg-bull/10 p-1.5 text-bull">
            <Activity size={18} />
          </div>
          <div className="leading-none">
            <h1 className="text-sm font-bold">Bursa</h1>
            <p className="text-[10px] text-subtle">IDX Monitor</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <nav className="flex items-center gap-1">
            <NavLink to="/" end className={linkClass}>
              <LayoutGrid size={14} /> Home
            </NavLink>
            <NavLink to="/watchlist" className={linkClass}>
              <Star size={14} /> Watchlist
            </NavLink>
          </nav>
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}
