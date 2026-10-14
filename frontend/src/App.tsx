import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import NavBar from './components/NavBar'
import Home from './pages/Home'

// Watchlist is a secondary route — load it on demand.
const Watchlist = lazy(() => import('./pages/Watchlist'))

// App shell: persistent top navigation + routed pages (full-width layout).
export default function App() {
  return (
    <div className="min-h-full bg-app text-ink">
      <NavBar />
      <Suspense
        fallback={<div className="w-full px-3 py-6 text-sm text-subtle">Loading…</div>}
      >
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/watchlist" element={<Watchlist />} />
        </Routes>
      </Suspense>
    </div>
  )
}
