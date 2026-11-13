import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { api as http, errorMessage } from '../api'

/**
 * Short messages at the bottom of the screen ("Saved"), and deleting with Undo:
 * the item disappears at once, and the real delete runs only after a few seconds
 * unless Undo is pressed. Timers live here, not in the page, so a delete still
 * happens after you navigate away; closing the tab sends pending deletes at once.
 */

const SHOW_MS = 3500
const UNDO_MS = 6000

interface Toast {
  id: number
  message: string
  tone: 'info' | 'error'
  undoKey?: string | undefined
}

interface PendingDelete {
  timer: ReturnType<typeof setTimeout>
  run: () => Promise<void>
}

interface UndoableDelete {
  /** Identifies the item while it waits, e.g. `tx:12`; see `isDeleting`. */
  key: string
  /** Names it in messages: "<label> deleted", "Couldn't delete <label>". */
  label: string
  /** Replaces "<label> deleted" (e.g. "BBCA removed from watchlist"). */
  message?: string | undefined
  commit: () => Promise<unknown>
  /** After the delete succeeds, e.g. invalidate queries (awaited before the item un-hides). */
  onDone?: (() => Promise<unknown> | void) | undefined
}

interface ToastApi {
  toast: (message: string, tone?: Toast['tone']) => void
  deleteWithUndo: (d: UndoableDelete) => void
  /** True while an item waits for its delete: hide it from lists. */
  isDeleting: (key: string) => boolean
}

const ToastContext = createContext<ToastApi | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const [deleting, setDeleting] = useState<ReadonlySet<string>>(new Set())
  const pending = useRef(new Map<string, PendingDelete>())
  const nextId = useRef(1)

  const dismiss = useCallback(
    (id: number) => setToasts((ts) => ts.filter((t) => t.id !== id)),
    [],
  )
  const show = useCallback(
    (t: Omit<Toast, 'id'>, ms: number) => {
      const id = nextId.current++
      setToasts((ts) => [...ts.slice(-2), { ...t, id }]) // at most 3 on screen
      setTimeout(() => dismiss(id), ms)
    },
    [dismiss],
  )
  const unhide = useCallback(
    (key: string) =>
      setDeleting((s) => {
        const n = new Set(s)
        n.delete(key)
        return n
      }),
    [],
  )

  const toast = useCallback<ToastApi['toast']>(
    (message, tone = 'info') => show({ message, tone }, SHOW_MS),
    [show],
  )

  const deleteWithUndo = useCallback<ToastApi['deleteWithUndo']>(
    ({ key, label, message, commit, onDone }) => {
      if (pending.current.has(key)) return
      const run = async () => {
        pending.current.delete(key)
        try {
          await commit()
          await onDone?.()
        } catch (e) {
          show(
            { message: errorMessage(e, `Couldn't delete ${label}.`), tone: 'error' },
            SHOW_MS,
          )
        } finally {
          unhide(key)
        }
      }
      pending.current.set(key, { timer: setTimeout(() => void run(), UNDO_MS), run })
      setDeleting((s) => new Set(s).add(key))
      show(
        { message: message ?? `${label} deleted`, tone: 'info', undoKey: key },
        UNDO_MS,
      )
    },
    [show, unhide],
  )

  const undo = (toastId: number, key: string) => {
    const p = pending.current.get(key)
    if (p) clearTimeout(p.timer)
    pending.current.delete(key)
    unhide(key)
    dismiss(toastId)
  }

  // Closing or reloading the tab: send the deletes now rather than drop them.
  useEffect(() => {
    const flush = () => {
      if (pending.current.size === 0) return
      // A page that's unloading cancels normal requests; keepalive ones finish.
      http.defaults.adapter = 'fetch'
      http.defaults.fetchOptions = { keepalive: true }
      for (const p of pending.current.values()) {
        clearTimeout(p.timer)
        void p.run()
      }
    }
    // Back from the back/forward cache: normal requests again.
    const restore = () => {
      delete http.defaults.adapter
      delete http.defaults.fetchOptions
    }
    window.addEventListener('pagehide', flush)
    window.addEventListener('pageshow', restore)
    return () => {
      window.removeEventListener('pagehide', flush)
      window.removeEventListener('pageshow', restore)
    }
  }, [])

  const api = useMemo<ToastApi>(
    () => ({ toast, deleteWithUndo, isDeleting: (key) => deleting.has(key) }),
    [toast, deleteWithUndo, deleting],
  )

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        role="status"
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-[calc(4.5rem+env(safe-area-inset-bottom))] z-[60] flex flex-col items-center gap-2 px-4 lg:bottom-6 print:hidden"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`pointer-events-auto flex animate-fade-in items-center gap-4 rounded-full py-2 pr-2 pl-4 text-xs font-medium shadow-pop ${
              t.tone === 'error' ? 'bg-bear text-white' : 'bg-ink text-app'
            } ${t.undoKey ? '' : 'pr-4'}`}
          >
            <span>{t.message}</span>
            {t.undoKey && (
              <button
                onClick={() => t.undoKey && undo(t.id, t.undoKey)}
                className="rounded-full bg-app/15 px-3 py-1 font-semibold transition hover:bg-app/25"
              >
                Undo
              </button>
            )}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>')
  return ctx
}
