import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import Footer from './components/Footer'
import NavBar from './components/NavBar'
import Home from './pages/Home'

// Secondary routes are loaded on demand.
const Watchlist = lazy(() => import('./pages/Watchlist'))
const Portfolio = lazy(() => import('./pages/Portfolio'))
const Screener = lazy(() => import('./pages/Screener'))
const Market = lazy(() => import('./pages/Market'))
const Alerts = lazy(() => import('./pages/Alerts'))

// App shell: persistent top nav + footer, routed pages (full-width layout).
export default function App() {
  return (
    <div className="flex min-h-full flex-col bg-app text-ink">
      <NavBar />
      <div className="flex-1">
        <Suspense
          fallback={<div className="w-full px-3 py-6 text-sm text-subtle">Loading…</div>}
        >
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/watchlist" element={<Watchlist />} />
            <Route path="/portfolio" element={<Portfolio />} />
            <Route path="/screener" element={<Screener />} />
            <Route path="/market" element={<Market />} />
            <Route path="/alerts" element={<Alerts />} />
          </Routes>
        </Suspense>
      </div>
      <Footer />
    </div>
  )
}
