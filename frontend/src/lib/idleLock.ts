import { useEffect } from 'react'
import { reportActivity } from '../api'

// The newest use of any tab of this browser (ms), so a busy tab keeps quiet ones open.
const ACTIVITY_KEY = 'bursa:last-activity'
// What counts as using the page. Background refreshes don't: the server only
// hears about activity through reportActivity().
const EVENTS = ['pointerdown', 'pointermove', 'keydown', 'wheel', 'touchstart', 'scroll']
const NOTE_EVERY = 5_000 // pointermove fires constantly; note it this often at most
const REPORT_EVERY = 60_000
const CHECK_EVERY = 10_000

function sharedActivity(): number {
  try {
    return Number(localStorage.getItem(ACTIVITY_KEY)) || 0
  } catch {
    return 0
  }
}

function shareActivity(at: number) {
  try {
    localStorage.setItem(ACTIVITY_KEY, String(at))
  } catch {
    // Private mode / blocked storage: this tab keeps its own time.
  }
}

/**
 * Lock after `minutes` without use (0 = never). The server enforces the same
 * limit from the activity reported here, so the page can't be kept open by
 * removing this timer; the timer just locks it on time.
 */
export function useIdleLock(minutes: number, onIdle: () => Promise<void>) {
  useEffect(() => {
    if (minutes <= 0) return
    const limit = minutes * 60_000
    let noted = Date.now() // showing the app (sign-in, unlock, reload) counts as use
    let reported = 0
    shareActivity(noted)

    const report = (now: number) => {
      reported = now
      void reportActivity().catch(() => undefined) // a 423 shows the lock screen
    }
    const onUse = () => {
      const now = Date.now()
      if (now - noted < NOTE_EVERY) return
      noted = now
      shareActivity(now)
      // At once after a quiet spell, so the server never sees a stale time.
      if (now - reported >= REPORT_EVERY) report(now)
    }
    const check = () => {
      if (Date.now() - Math.max(noted, sharedActivity()) >= limit) void onIdle()
    }

    report(noted)
    EVENTS.forEach((e) =>
      window.addEventListener(e, onUse, { passive: true, capture: true }),
    )
    // A sleeping laptop pauses timers: check as soon as the page is seen again.
    document.addEventListener('visibilitychange', check)
    const timer = window.setInterval(check, CHECK_EVERY)
    return () => {
      EVENTS.forEach((e) => window.removeEventListener(e, onUse, { capture: true }))
      document.removeEventListener('visibilitychange', check)
      window.clearInterval(timer)
    }
  }, [minutes, onIdle])
}
