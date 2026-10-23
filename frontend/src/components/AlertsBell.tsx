import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bell } from 'lucide-react'
import { useAlertEvents, usePreferences } from '../hooks'
import { fmtShortDateTime, parseServerTime } from '../lib/format'

// Where this browser kept the marker before it moved to the account.
const LEGACY_SEEN_KEY = 'bursa-alerts-seen'

const time = (iso: string | null) => parseServerTime(iso)?.getTime() ?? 0

/** Navbar bell: unread count + recent triggered alerts. */
export default function AlertsBell() {
  const { data: events = [] } = useAlertEvents()
  const { loaded, alertsSeenAt, markAlertsSeen } = usePreferences()
  const [open, setOpen] = useState(false)

  // One-time move of the old per-browser "seen" marker to the account (runs once loaded).
  useEffect(() => {
    if (!loaded) return
    let legacy: string | null = null
    try {
      legacy = localStorage.getItem(LEGACY_SEEN_KEY)
      localStorage.removeItem(LEGACY_SEEN_KEY)
    } catch {
      /* storage unavailable */
    }
    if (legacy && !alertsSeenAt) markAlertsSeen(legacy)
  }, [loaded, alertsSeenAt, markAlertsSeen]) // the key is gone after the first run

  // Seen is per account, so reading alerts on one device clears the badge on all.
  const seen = time(alertsSeenAt)
  const unread = loaded ? events.filter((e) => time(e.triggered_at) > seen).length : 0

  const toggle = () => {
    const next = !open
    setOpen(next)
    const newest = events[0] // newest first
    if (next && unread > 0 && newest) markAlertsSeen(newest.triggered_at)
  }

  return (
    <div className="relative">
      <button
        onClick={toggle}
        title="Alerts"
        aria-label="Alerts"
        className="relative rounded-sm p-2 text-muted ring-1 ring-line-strong transition hover:bg-panelalt hover:text-ink"
      >
        <Bell size={15} />
        {unread > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-sm bg-bear px-1 text-[9px] font-semibold text-white">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-20 mt-1 w-80 animate-fade-in overflow-hidden rounded-md bg-panel shadow-pop ring-1 ring-line-strong">
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
                  {fmtShortDateTime(e.triggered_at)}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
