/** Add the stock to the watchlist or remove it (self-contained). */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Star } from 'lucide-react'
import { addToWatchlist, removeFromWatchlist } from '../../api'
import { useWatchlist } from '../../hooks'

export default function WatchButton({ ticker }: { ticker: string }) {
  const queryClient = useQueryClient()
  const watchlist = useWatchlist()
  const watched = (watchlist.data ?? []).some((w) => w.ticker === ticker)
  const invalidateWatch = () => queryClient.invalidateQueries({ queryKey: ['watchlist'] })
  const add = useMutation({
    mutationFn: () => addToWatchlist(ticker),
    onSuccess: invalidateWatch,
  })
  const remove = useMutation({
    mutationFn: () => removeFromWatchlist(ticker),
    onSuccess: invalidateWatch,
  })
  const watchPending = add.isPending || remove.isPending
  return (
    <button
      onClick={() => (watched ? remove.mutate() : add.mutate())}
      disabled={watchPending}
      title={watched ? 'Remove from watchlist' : 'Add to watchlist'}
      className={`flex items-center gap-1 rounded px-2.5 py-1.5 text-xs font-medium ring-1 transition disabled:opacity-50 ${
        watched
          ? 'text-accent ring-accent/40 hover:bg-accent/10'
          : 'text-muted ring-line-strong hover:bg-panelalt hover:text-ink'
      }`}
    >
      <Star size={14} className={watched ? 'fill-current' : ''} />
      {watched ? 'Watching' : 'Watch'}
    </button>
  )
}
