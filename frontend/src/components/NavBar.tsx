import { NavLink } from 'react-router-dom'
import { Activity, LayoutGrid, Star } from 'lucide-react'

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition ${
    isActive
      ? 'bg-panelalt text-white'
      : 'text-slate-400 hover:bg-panelalt hover:text-white'
  }`

export default function NavBar() {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-800 bg-panel/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-3">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-bull/10 p-2 text-bull">
            <Activity size={20} />
          </div>
          <div>
            <h1 className="text-base font-bold leading-tight">Bursa</h1>
            <p className="text-[11px] text-slate-500">IDX Monitor</p>
          </div>
        </div>

        <nav className="flex items-center gap-1">
          <NavLink to="/" end className={linkClass}>
            <LayoutGrid size={15} /> Home
          </NavLink>
          <NavLink to="/watchlist" className={linkClass}>
            <Star size={15} /> Watchlist
          </NavLink>
        </nav>
      </div>
    </header>
  )
}
