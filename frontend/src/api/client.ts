import axios from 'axios'

// Configurable via VITE_API_URL (set in docker-compose / .env). Falls back to
// localhost for running `npm run dev` outside Docker.
const baseURL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export const api = axios.create({ baseURL, timeout: 15_000 })

// Mirror of the backend INDEX_ORDER. Used as a fallback so the selector is
// always fully populated, even before/if the /api/indexes request resolves.
export const DEFAULT_INDEXES = ['LQ45', 'IDX30', 'JII', 'ISSI', 'IDXHIDIV20', 'IDXBUMN20']
