import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Bell } from 'lucide-react'
import { useAlertEvents } from '../hooks'

const SEEN_KEY = 'bursa-alerts-seen'

/** Navbar bell: unread count + recent triggered alerts. */
export default function AlertsBell() {
  const { data: events = [] } = useAlertEvents()
  const [open, setOpen] = useState(false)
  const [seenAt, setSeenAt] = useState<string>(() => {
    try {
      return localStorage.getItem(SEEN_KEY) ?? ''
    } catch {
      return ''
    }
  })

  const unread = events.filter((e) => e.triggered_at > seenAt).length

  const toggle = () => {
    const next = !open
    setOpen(next)
    if (next && events.length > 0) {
      // Mark up to the newest event as seen (string compare keeps the format stable).
      const newest = events[0].triggered_at
      setSeenAt(newest)
      try {
        localStorage.setItem(SEEN_KEY, newest)
      } catch {
        /* ignore */
      }
    }
  }

  return (
    <div className="relative">
      <button
        onClick={toggle}
        title="Alerts"
        aria-label="Alerts"
        className="relative rounded p-1.5 text-muted ring-1 ring-line transition hover:bg-panelalt hover:text-ink"
      >
        <Bell size={15} />
        {unread > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded bg-bear px-1 text-[9px] font-semibold text-white">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-20 mt-1 w-80 animate-fade-in overflow-hidden rounded-md bg-panel shadow-pop ring-1 ring-line">
          <div className="flex items-center justify-between border-b border-line px-3 py-2">
            <span className="text-xs font-semibold">Alerts</span>
            <Link
              to="/alerts"
              onClick={() => setOpen(false)}
              className="text-[11px] text-muted hover:text-ink"
            >
              Manage →
            </Link>
          </div>
          <ul className="max-h-80 divide-y divide-line overflow-y-auto">
            {events.length === 0 && (
              <li className="px-3 py-6 text-center text-xs text-subtle">
                No alerts triggered yet.
              </li>
            )}
            {events.map((e) => (
              <li key={e.id} className="px-3 py-2">
                <div className="text-xs text-ink">{e.message}</div>
                <div className="mt-0.5 text-[10px] text-subtle">
                  {new Date(e.triggered_at).toLocaleString('en-GB', {
                    day: '2-digit',
                    month: 'short',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
