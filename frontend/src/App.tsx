import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import Footer from './components/Footer'
import NavBar from './components/NavBar'
import WeakPasswordBanner from './components/WeakPasswordBanner'
import { useAuth } from './lib/auth'
import Home from './pages/Home'
import Login from './pages/auth/Login'

// Secondary routes are loaded on demand.
const Watchlist = lazy(() => import('./pages/Watchlist'))
const Portfolio = lazy(() => import('./pages/Portfolio'))
const Screener = lazy(() => import('./pages/Screener'))
const Market = lazy(() => import('./pages/Market'))
const Alerts = lazy(() => import('./pages/Alerts'))
const Browse = lazy(() => import('./pages/Browse'))
const DataHealth = lazy(() => import('./pages/DataHealth'))
const Settings = lazy(() => import('./pages/Settings'))
const SetupTwoFactor = lazy(() => import('./pages/auth/SetupTwoFactor'))
const ChangeWeakPassword = lazy(() => import('./pages/auth/ChangeWeakPassword'))
const AcceptInvite = lazy(() => import('./pages/auth/AcceptInvite'))
const ResetPassword = lazy(() => import('./pages/auth/ResetPassword'))
const ForgotPassword = lazy(() => import('./pages/auth/ForgotPassword'))

const loading = <div className="w-full px-3 py-6 text-sm text-subtle">Loading…</div>

// Every page needs a signed-in user; invite / reset links work signed out.
export default function App() {
  const { user, isAdmin } = useAuth()

  return (
    <Suspense fallback={loading}>
      <Routes>
        <Route path="/invite/:token" element={<AcceptInvite />} />
        <Route path="/reset/:token" element={<ResetPassword />} />
        <Route
          path="/forgot"
          element={user ? <Navigate to="/" replace /> : <ForgotPassword />}
        />
        <Route
          path="*"
          element={
            user === undefined ? (
              <div className="min-h-full bg-app" /> // checking the session
            ) : user === null ? (
              <Login />
            ) : user.mfa_setup_required ? (
              <SetupTwoFactor /> // admins: 2FA first
            ) : user.password_change_required ? (
              <ChangeWeakPassword /> // admins: then a strong password
            ) : (
              <Shell isAdmin={isAdmin} />
            )
          }
        />
      </Routes>
    </Suspense>
  )
}

// App shell: persistent top nav + footer, routed pages (full-width layout).
function Shell({ isAdmin }: { isAdmin: boolean }) {
  return (
    <div className="flex min-h-full flex-col bg-app text-ink">
      <NavBar />
      <WeakPasswordBanner />
      <div className="flex-1">
        <Suspense fallback={loading}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/watchlist" element={<Watchlist />} />
            <Route path="/portfolio" element={<Portfolio />} />
            <Route path="/screener" element={<Screener />} />
            <Route path="/market" element={<Market />} />
            <Route path="/alerts" element={<Alerts />} />
            <Route path="/browse" element={<Browse />} />
            {isAdmin && <Route path="/data" element={<DataHealth />} />}
            <Route path="/settings/:section?" element={<Settings />} />
            {/* Old addresses, kept for bookmarks. */}
            <Route
              path="/account/security"
              element={<Navigate to="/settings/security" replace />}
            />
            <Route
              path="/admin/users"
              element={<Navigate to="/settings/users" replace />}
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </div>
      <Footer />
    </div>
  )
}
