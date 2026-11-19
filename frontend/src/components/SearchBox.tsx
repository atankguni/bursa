import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Search } from 'lucide-react'
import {
  fetchStock,
  searchSymbols,
  trackStock,
  type SearchResult,
  type Stock,
} from '../api'
import { queryKeys } from '../hooks'
import { useAuth } from '../lib/auth'
import StockDetailModal from './StockDetailModal'

/**
 * Navbar symbol search — click a result to inspect it in the detail modal.
 * `full`: fill the available width (the phone search row).
 */
export default function SearchBox({
  full = false,
  autoFocus = false,
}: {
  full?: boolean
  autoFocus?: boolean
}) {
  // Only admins grow the tracked universe (it costs data-provider calls).
  const { isAdmin } = useAuth()
  const [q, setQ] = useState('')
  const [debounced, setDebounced] = useState('')
  const [open, setOpen] = useState(false)
  const [showAll, setShowAll] = useState(false)
  const [selected, setSelected] = useState<Stock | null>(null)
  const [preparing, setPreparing] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  // The highlighted result for ↑/↓/Enter, reset to the first whenever the query changes.
  const [active, setActive] = useState({ q: '', i: 0 })
  const ref = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLInputElement>(null)
  const qc = useQueryClient()

  // ⌘K / Ctrl+K anywhere, or "/" outside a text field, jumps to the search
  // (the desktop box only: the phone row has its own button).
  useEffect(() => {
    if (full) return
    function onKey(e: KeyboardEvent) {
      const t = e.target
      const typing =
        t instanceof HTMLElement &&
        (t.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName))
      if (
        ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') ||
        (e.key === '/' && !typing)
      ) {
        if (!input.current || input.current.offsetParent === null) return // hidden
        e.preventDefault()
        input.current.focus()
        input.current.select()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [full])
  const mac =
    typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform)

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 300)
    return () => clearTimeout(t)
  }, [q])

  // Close the results on any click outside.
  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && e.target instanceof Node && !ref.current.contains(e.target))
        setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const { data: results = [], isFetching } = useQuery({
    queryKey: queryKeys.search(debounced, showAll),
    queryFn: () => searchSymbols(debounced, showAll),
    enabled: debounced.length >= 2,
  })

  const shown = open && debounced.length >= 2
  const activeIndex =
    active.q === debounced ? Math.min(active.i, Math.max(results.length - 1, 0)) : 0
  const listId = `${full ? 'm' : 'd'}-search-results`

  const openPreview = async (r: SearchResult) => {
    setOpen(false)
    setError(null)
    setPreparing(r.symbol)
    try {
      // Ensure the ticker is tracked so the info endpoints can serve it.
      if (isAdmin) {
        try {
          await trackStock(r.symbol, r.name)
        } catch {
          /* already tracked (409) or transient — ignore */
        }
      }
      const stock = await fetchStock(r.symbol)
      setSelected(stock)
      void qc.invalidateQueries({ queryKey: ['stocks'] })
      setQ('')
    } catch {
      setError(`Could not load ${r.symbol}`)
    } finally {
      setPreparing(null)
    }
  }

  return (
    <div ref={ref} className={`relative ${full ? 'w-full' : ''}`}>
      <div className="flex items-center gap-2 rounded-sm bg-panelalt py-1.5 pr-2 pl-3 text-xs transition-shadow focus-within:bg-panel focus-within:ring-2 focus-within:ring-accent">
        <Search size={14} className="text-muted" />
        <input
          ref={input}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              setOpen(false)
              e.currentTarget.blur()
            } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
              e.preventDefault()
              if (!shown) return setOpen(true)
              if (results.length === 0) return
              const step = e.key === 'ArrowDown' ? 1 : -1
              setActive({
                q: debounced,
                i: (activeIndex + step + results.length) % results.length,
              })
            } else if (e.key === 'Enter' && shown && preparing == null) {
              const r = results[activeIndex]
              if (r) {
                e.preventDefault()
                void openPreview(r)
              }
            }
          }}
          role="combobox"
          aria-expanded={shown}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={
            shown && results[activeIndex] ? `${listId}-${activeIndex}` : undefined
          }
          value={q}
          onChange={(e) => {
            setQ(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          autoFocus={autoFocus}
          placeholder="Search ticker…"
          aria-label="Search ticker"
          className={`${full ? 'min-w-0 flex-1 text-base sm:text-xs' : 'w-36 xl:w-44'} bg-transparent text-ink outline-hidden placeholder:text-subtle`}
        />
        {!full && !q && (
          <kbd
            aria-hidden
            className="hidden rounded-xs bg-panel px-1.5 py-0.5 font-sans text-2xs text-subtle ring-1 ring-line xl:inline"
          >
            {mac ? '⌘K' : 'Ctrl K'}
          </kbd>
        )}
      </div>

      {error && (
        <div className="absolute left-0 z-30 mt-1 whitespace-nowrap rounded-sm bg-panel px-2.5 py-1 text-2xs text-bear shadow-pop ring-1 ring-line">
          {error}
        </div>
      )}

      {shown && (
        <div
          id={listId}
          role="listbox"
          aria-label="Search results"
          className={`absolute left-0 z-20 mt-1 ${full ? 'right-0' : 'w-80'} animate-fade-in overflow-hidden rounded-md bg-panel p-1 shadow-pop ring-1 ring-line`}
        >
          {isAdmin && (
            <label className="mb-1 flex cursor-pointer items-center justify-between border-b border-line px-2.5 py-1.5 text-2xs text-muted">
              <span>All exchanges</span>
              <input
                type="checkbox"
                checked={showAll}
                onChange={(e) => setShowAll(e.target.checked)}
                className="h-3.5 w-3.5 accent-bull"
              />
            </label>
          )}

          {isFetching && results.length === 0 && (
            <div className="px-3 py-2 text-xs text-subtle">Searching…</div>
          )}
          {!isFetching && results.length === 0 && (
            <div className="px-3 py-2 text-xs text-subtle">No matches</div>
          )}
          {results.map((r, i) => (
            <button
              key={r.symbol}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === activeIndex}
              tabIndex={-1}
              onClick={() => void openPreview(r)}
              onMouseMove={() => i !== activeIndex && setActive({ q: debounced, i })}
              disabled={preparing != null}
              className={`flex w-full items-center justify-between gap-2 rounded-sm px-2.5 py-1.5 text-left text-xs transition disabled:opacity-50 ${
                i === activeIndex ? 'bg-panelalt' : ''
              }`}
            >
              <span className="min-w-0">
                <span className="font-medium text-ink">{r.symbol}</span>
                <span className="ml-2 truncate text-subtle">{r.name}</span>
              </span>
              <span className="shrink-0 text-subtle">
                {preparing === r.symbol ? (
                  <Loader2 size={12} className="animate-spin" />
                ) : (
                  <span className="text-2xs">{r.exchange}</span>
                )}
              </span>
            </button>
          ))}
        </div>
      )}

      {selected && (
        <StockDetailModal stock={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  )
}
