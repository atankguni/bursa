import { Route, Routes } from 'react-router-dom'
import NavBar from './components/NavBar'
import Home from './pages/Home'
import Watchlist from './pages/Watchlist'

// App shell: persistent top navigation + routed pages (full-width layout).
export default function App() {
  return (
    <div className="min-h-full bg-app text-ink">
      <NavBar />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/watchlist" element={<Watchlist />} />
      </Routes>
    </div>
  )
}
