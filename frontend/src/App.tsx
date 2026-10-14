import { Route, Routes } from 'react-router-dom'
import NavBar from './components/NavBar'
import Home from './pages/Home'
import Watchlist from './pages/Watchlist'

// App shell: persistent top navigation + routed pages.
export default function App() {
  return (
    <div className="min-h-full bg-slate-950">
      <NavBar />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/watchlist" element={<Watchlist />} />
      </Routes>
    </div>
  )
}
