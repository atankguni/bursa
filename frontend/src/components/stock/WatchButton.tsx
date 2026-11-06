/** Add the stock to the watchlist or remove it (self-contained). */
import { Loader2, Star } from 'lucide-react'
import { useWatchToggle } from '../../hooks'

export default function WatchButton({ ticker }: { ticker: string }) {
  const { isWatched, isPending, toggle, error } = useWatchToggle()
  // Shows the new state at the click; the spinner says it's still being saved.
  const watched = isWatched(ticker)
  const busy = isPending(ticker)
  return (
    <span className="flex items-center gap-2">
      {error && (
        <span
          role="alert"
          className="max-w-48 truncate text-[11px] text-bear"
          title={error}
        >
          {error}
        </span>
      )}
      <button
        onClick={() => toggle(ticker)}
        aria-busy={busy}
        title={watched ? 'Remove from watchlist' : 'Add to watchlist'}
        className={`flex items-center gap-1 rounded-sm px-2.5 py-1.5 text-xs font-medium ring-1 transition ${
          watched
            ? 'text-accent ring-accent/40 hover:bg-accent/10'
            : 'text-muted ring-line-strong hover:bg-panelalt hover:text-ink'
        } ${busy ? 'cursor-progress' : ''}`}
      >
        {busy ? (
          <Loader2 size={14} className="animate-spin" aria-hidden />
        ) : (
          <Star size={14} className={watched ? 'fill-current' : ''} aria-hidden />
        )}
        {watched ? 'Watching' : 'Watch'}
      </button>
    </span>
  )
}
