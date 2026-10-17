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
import StockDetailModal from './StockDetailModal'

/** Navbar symbol search — click a result to inspect it in the detail modal. */
export default function SearchBox() {
  const [q, setQ] = useState('')
  const [debounced, setDebounced] = useState('')
  const [open, setOpen] = useState(false)
  const [showAll, setShowAll] = useState(false)
  const [selected, setSelected] = useState<Stock | null>(null)
  const [preparing, setPreparing] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const ref = useRef<HTMLDivElement>(null)
  const qc = useQueryClient()

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 300)
    return () => clearTimeout(t)
  }, [q])

  // Close the results on any click outside.
  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const { data: results = [], isFetching } = useQuery({
    queryKey: queryKeys.search(debounced, showAll),
    queryFn: () => searchSymbols(debounced, showAll),
    enabled: debounced.length >= 2,
  })

  const openPreview = async (r: SearchResult) => {
    setOpen(false)
    setError(null)
    setPreparing(r.symbol)
    try {
      // Ensure the ticker is tracked so the info endpoints can serve it.
      try {
        await trackStock(r.symbol, r.name)
      } catch {
        /* already tracked (409) or transient — ignore */
      }
      const stock = await fetchStock(r.symbol)
      setSelected(stock)
      qc.invalidateQueries({ queryKey: ['stocks'] })
      setQ('')
    } catch {
      setError(`Could not load ${r.symbol}`)
    } finally {
      setPreparing(null)
    }
  }

  return (
    <div ref={ref} className="relative">
      <div className="flex items-center gap-1.5 rounded bg-panelalt/70 py-1.5 pl-2.5 pr-2 text-xs ring-1 ring-line-strong focus-within:ring-accent">
        <Search size={13} className="text-muted" />
        <input
          value={q}
          onChange={(e) => {
            setQ(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          placeholder="Search ticker…"
          className="w-44 bg-transparent text-ink outline-none placeholder:text-subtle"
        />
      </div>

      {error && (
        <div className="absolute left-0 z-30 mt-1 whitespace-nowrap rounded bg-panel px-2.5 py-1 text-[11px] text-bear shadow-pop ring-1 ring-line">
          {error}
        </div>
      )}

      {open && debounced.length >= 2 && (
        <div className="absolute left-0 z-20 mt-1 w-80 animate-fade-in overflow-hidden rounded-md bg-panel p-1 shadow-pop ring-1 ring-line-strong">
          <label className="mb-1 flex cursor-pointer items-center justify-between border-b border-line px-2.5 py-1.5 text-[11px] text-muted">
            <span>All exchanges</span>
            <input
              type="checkbox"
              checked={showAll}
              onChange={(e) => setShowAll(e.target.checked)}
              className="h-3.5 w-3.5 accent-bull"
            />
          </label>

          {isFetching && results.length === 0 && (
            <div className="px-3 py-2 text-xs text-subtle">Searching…</div>
          )}
          {!isFetching && results.length === 0 && (
            <div className="px-3 py-2 text-xs text-subtle">No matches</div>
          )}
          {results.map((r) => (
            <button
              key={r.symbol}
              onClick={() => openPreview(r)}
              disabled={preparing != null}
              className="flex w-full items-center justify-between gap-2 rounded px-2.5 py-1.5 text-left text-xs transition hover:bg-panelalt disabled:opacity-50"
            >
              <span className="min-w-0">
                <span className="font-medium text-ink">{r.symbol}</span>
                <span className="ml-2 truncate text-subtle">{r.name}</span>
              </span>
              <span className="shrink-0 text-subtle">
                {preparing === r.symbol ? (
                  <Loader2 size={12} className="animate-spin" />
                ) : (
                  <span className="text-[10px]">{r.exchange}</span>
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
