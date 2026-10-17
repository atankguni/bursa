import axios from 'axios'

// Configurable via VITE_API_URL (set in docker-compose / .env). Falls back to
// localhost for running `npm run dev` outside Docker.
const baseURL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// withCredentials: send the HttpOnly session cookie (dev runs the API on :8000).
export const api = axios.create({ baseURL, timeout: 15_000, withCredentials: true })

/** Fired when the API answers 401 (session expired or signed out elsewhere). */
export const UNAUTHORIZED_EVENT = 'bursa:unauthorized'

api.interceptors.response.use(undefined, (error) => {
  const url: string = error?.config?.url ?? ''
  // The sign-in calls report their own 401s ("wrong password"); everything else
  // means the session is gone, so the app returns to the sign-in screen.
  if (error?.response?.status === 401 && !url.startsWith('/api/auth/')) {
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
  }
  return Promise.reject(error)
})

/** The API's `detail` message from a failed request, or `fallback`. */
export function errorMessage(error: unknown, fallback: string): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data
    ?.detail
  return typeof detail === 'string' ? detail : fallback
}

// Mirror of the backend INDEX_ORDER. Used as a fallback so the selector is
// always fully populated, even before/if the /api/indexes request resolves.
export const DEFAULT_INDEXES = ['LQ45', 'IDX30', 'JII', 'ISSI', 'IDXHIDIV20', 'IDXBUMN20']
