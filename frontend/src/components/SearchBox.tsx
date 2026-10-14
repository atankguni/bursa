import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Search } from 'lucide-react'
import { searchSymbols, trackStock } from '../api'
import { queryKeys } from '../hooks'

/** Navbar symbol search that can add an arbitrary ticker to the universe. */
export default function SearchBox() {
  const [q, setQ] = useState('')
  const [debounced, setDebounced] = useState('')
  const [open, setOpen] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const qc = useQueryClient()

  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 300)
    return () => clearTimeout(t)
  }, [q])

  const { data: results = [], isFetching } = useQuery({
    queryKey: queryKeys.search(debounced),
    queryFn: () => searchSymbols(debounced),
    enabled: debounced.length >= 2,
  })

  const track = useMutation({
    mutationFn: ({ symbol, name }: { symbol: string; name: string }) =>
      trackStock(symbol, name),
    onSuccess: (s) => {
      qc.invalidateQueries({ queryKey: ['stocks'] })
      qc.invalidateQueries({ queryKey: ['indexes'] })
      setMessage(`Tracking ${s.ticker}`)
      setQ('')
      setOpen(false)
      setTimeout(() => setMessage(null), 2500)
    },
    onError: (e: unknown) => {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Could not add ticker'
      setMessage(detail)
      setTimeout(() => setMessage(null), 3000)
    },
  })

  return (
    <div className="relative">
      <div className="flex items-center gap-1.5 rounded-full bg-panelalt/70 py-1 pl-2.5 pr-2 text-xs ring-1 ring-line focus-within:ring-bull">
        <Search size={13} className="text-muted" />
        <input
          value={q}
          onChange={(e) => {
            setQ(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          placeholder="Search ticker…"
          className="w-36 bg-transparent text-ink outline-none placeholder:text-subtle"
        />
      </div>

      {message && (
        <div className="absolute right-0 z-30 mt-1 whitespace-nowrap rounded-lg bg-panel px-2.5 py-1 text-[11px] text-muted shadow-pop ring-1 ring-line">
          {message}
        </div>
      )}

      {open && debounced.length >= 2 && !message && (
        <div className="absolute right-0 z-20 mt-1 w-72 animate-fade-in overflow-hidden rounded-xl bg-panel p-1 shadow-pop ring-1 ring-line">
          {isFetching && results.length === 0 && (
            <div className="px-3 py-2 text-xs text-subtle">Searching…</div>
          )}
          {!isFetching && results.length === 0 && (
            <div className="px-3 py-2 text-xs text-subtle">No matches</div>
          )}
          {results.map((r) => (
            <button
              key={r.symbol}
              onClick={() => track.mutate({ symbol: r.symbol, name: r.name })}
              disabled={track.isPending}
              className="flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs transition hover:bg-panelalt disabled:opacity-50"
            >
              <span className="min-w-0">
                <span className="font-medium text-ink">{r.symbol}</span>
                <span className="ml-2 truncate text-subtle">{r.name}</span>
              </span>
              <span className="flex shrink-0 items-center gap-1 text-subtle">
                <span className="text-[10px]">{r.exchange}</span>
                <Plus size={12} />
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
