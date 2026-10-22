import axios, { isAxiosError } from 'axios'

// Configurable via VITE_API_URL (set in docker-compose / .env). Falls back to
// localhost for running `npm run dev` outside Docker.
const baseURL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// withCredentials: send the HttpOnly session cookie (dev runs the API on :8000).
export const api = axios.create({ baseURL, timeout: 15_000, withCredentials: true })

/** Fired when the API answers 401 (session expired or signed out elsewhere). */
export const UNAUTHORIZED_EVENT = 'bursa:unauthorized'
/** Fired when an admin must first set up two-factor authentication or change a
 * weak password (403): /me is re-read, which shows the matching screen. */
export const MFA_SETUP_EVENT = 'bursa:mfa-setup-required'
const ACCOUNT_POLICY = ['two_factor_setup_required', 'password_change_required']

api.interceptors.response.use(undefined, (error: unknown) => {
  const url = isAxiosError(error) ? (error.config?.url ?? '') : ''
  const status = errorStatus(error)
  // The sign-in calls report their own 401s ("wrong password"); everything else
  // means the session is gone, so the app returns to the sign-in screen.
  if (status === 401 && !url.startsWith('/api/auth/')) {
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))
  }
  const detail = errorDetail(error)
  if (status === 403 && detail && ACCOUNT_POLICY.includes(detail)) {
    window.dispatchEvent(new Event(MFA_SETUP_EVENT))
  }
  return Promise.reject(error)
})

/** HTTP status of a failed request (undefined: not an HTTP error, e.g. offline). */
export function errorStatus(error: unknown): number | undefined {
  return isAxiosError(error) ? error.response?.status : undefined
}

/** The API's `detail` text from a failed request (FastAPI's error body), if any. */
export function errorDetail(error: unknown): string | undefined {
  if (!isAxiosError(error)) return undefined
  const body: unknown = error.response?.data
  if (typeof body !== 'object' || body === null || !('detail' in body)) return undefined
  return typeof body.detail === 'string' ? body.detail : undefined
}

/** The API's `detail` message from a failed request, or `fallback`. */
export function errorMessage(error: unknown, fallback: string): string {
  return errorDetail(error) ?? fallback
}

// Mirror of the backend INDEX_ORDER. Used as a fallback so the selector is
// always fully populated, even before/if the /api/indexes request resolves.
export const DEFAULT_INDEXES = ['LQ45', 'IDX30', 'JII', 'ISSI', 'IDXHIDIV20', 'IDXBUMN20']
